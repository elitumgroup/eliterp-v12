# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BankRecordsCancel(models.TransientModel):
    _name = 'account.bank.records.cancel'

    _description = _('Ventana para cancelar registros bancarios')

    description = fields.Text('Descripción', required=True)
    record_id = fields.Many2one('account.payment', 'Registro bancario')

    @api.multi
    def confirm_cancel(self):
        """
        Cancelamos depósito/transferencia (Registros bancarios)
        :return:
        """
        move = self.record_id.move_id
        move.reverse_moves(move.date, move.journal_id or False)
        move.write({'state': 'cancel', 'ref': self.description})
        self.record_id.update({'state': 'cancelled'})
        return True


class Payment(models.Model):
    _inherit = "account.payment"

    @api.onchange('amount', 'currency_id')
    def _onchange_amount(self):
        """
        MM: Lo cambiamos porqué sale error en moneda
        """
        return

    @api.multi
    def action_button_cancel(self):
        """
        Abrimos venta emergente para cancelar depósito/transferencia si està
        en estado borrador cancelamos la misma
        :return: dict
        """
        if self.state == 'draft':
            return self.write({'state': 'cancelled'})
        context = {
            'default_record_id': self.id
        }
        return {
            'name': _("Explique la razón"),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'account.bank.records.cancel',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }

    @api.model
    def create(self, vals):
        """
        MM: Creamos nuevo registro y validamos período contable
        :param vals:
        :return: object
        """
        if 'date_payment' in vals:
            self.env['account.period'].valid_period(vals['date_payment'])
        res = super(Payment, self).create(vals)
        return res

    @api.multi
    def post_transfer(self):
        """
        Confirmamos la transferencia, creamos el asiento contable con los datos ingresados
        :return:
        """
        company = self.company_id
        domain = [
            ('name', '=', 'Transferencia bancaria'),
            ('company_id', '=', company.id)
        ]
        journal = self.env['account.journal'].search(domain, limit=1)
        if not journal:
            raise UserError(_("No está definido el diario (Transferencia bancaria) para compañía: %s") % company.name)
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': self.payment_date,
            'ref': self.communication or '/'
        })
        self.env['account.move.line'].with_context(check_move_validity=False).create(
            {'name': self.communication,
             'journal_id': journal.id,
             'account_id': self.journal_id.default_debit_account_id.id,
             'move_id': move.id,
             'credit': 0.0,
             'debit': self.amount,
             'date': self.payment_date,
             })
        self.env['account.move.line'].with_context(check_move_validity=True).create(
            {'name': _("De ") + self.journal_id.name + _(" a ") + self.destination_journal_id.name,
             'journal_id': journal.id,
             'account_id': self.destination_journal_id.default_credit_account_id.id,
             'move_id': move.id,
             'credit': self.amount,
             'debit': 0.0,
             'date': self.payment_date
             })
        move.post()
        return self.write({
            'state': 'posted',
            'name': move.name,
            'move_id': move.id
        })

    @api.multi
    def unlink(self):
        for record in self:
            if record.move_id:
                raise UserError(_(
                    'No puedes borrar un registro bancario con asiento contable.'))
        return super(Payment, self).unlink()

    name = fields.Char(readonly=True, copy=False, default="Nuevo")  # CM
    journal_id = fields.Many2one('account.journal', domain=None)  # CM TODO: Revisar soló salgan diarios tipo banco
    move_id = fields.Many2one('account.move', string="Asiento contable", readonly=True)
    company_id = fields.Many2one('res.company', related=False, string='Compañía', readonly=False,
                                 default=lambda self: self.env.user.company_id)  # CM
    # Campos para depósitos bancarios
    type_deposit = fields.Selection([
        ('cash', 'Depósito directo (Efectivo)'),
        ('external_checks', 'Cheques externos')
    ], string="Tipo de depósito", default='cash')

    def _get_move_lines(self, move_line, move_id):
        """
        Creamos líneas de movimiento contable dependiendo del tipo de depósito
        :return:
        """
        if self.type_deposit == 'cash':
            for line in self.deposit_line_cash:
                move_line.create({
                    'name': line.reference or '/',
                    'journal_id': move_id.journal_id.id,
                    'account_id': line.account_id.id,
                    'move_id': move_id.id,
                    'debit': 0.0,
                    'credit': line.amount,
                    'date': self.payment_date,
                })
        if self.type_deposit == 'external_checks':
            for line in self.deposit_line_external_checks:
                move_line.create({
                    'name': "%s: %s" % (line.bank_id.name, line.check_number),
                    'journal_id': move_id.journal_id.id,
                    'account_id': line.account_id.id,
                    'move_id': move_id.id,
                    'debit': 0.0,
                    'credit': line.amount,
                    'date': self.payment_date,
                })

    @api.multi
    def post_deposit(self):
        """
        Confirmamos el depósito, creamos el asiento contable con los datos ingresados
        :return:
        """
        company = self.company_id
        domain = [
            ('name', '=', 'Depósito bancario'),
            ('company_id', '=', company.id)
        ]
        journal = self.env['account.journal'].search(domain, limit=1)
        if not journal:
            raise UserError(_("No está definido el diario (Depósito bancario) para compañía: %s") % company.name)
        move_id = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': self.payment_date,
            'ref': self.communication or '/'
        })
        move_line = self.env['account.move.line'].with_context(check_move_validity=False)
        self._get_move_lines(move_line, move_id)  # Creamos líneas contables
        # Creamos línea de acreditación a la cuenta bancaria del diario
        self.env['account.move.line'].with_context(check_move_validity=True).create({
            'name': "%s: %s" % (self.journal_id.name, self.communication or '/'),
            'journal_id': journal.id,
            'account_id': self.journal_id.default_credit_account_id.id,
            'move_id': move_id.id,
            'debit': self.amount,
            'credit': 0.0,
            'date': self.payment_date,
        })
        move_id.post()
        return self.write({
            'state': 'posted',
            'name': move_id.name,
            'move_id': move_id.id
        })

    def _get_amount(self):
        total = 0.00
        if self.type_deposit == 'external_checks':
            for line in self.deposit_line_external_checks:
                total += line.amount
        if self.type_deposit == 'cash':
            for line in self.deposit_line_cash:
                total += line.amount
        return total

    @api.multi
    def load_amount(self):
        """
        Sumar monto de cada línea de depósito dependiendo del tipo
        :return:
        """
        total = self._get_amount()
        return self.update({'amount': total})

    deposit_line_cash = fields.One2many('account.deposit.line.cash', 'payment_id', readonly=True,
                                        states={'draft': [('readonly', False)]},
                                        string='Líneas de efectivo')
    deposit_line_external_checks = fields.One2many('account.deposit.line.external.checks', 'payment_id', readonly=True,
                                                   states={'draft': [('readonly', False)]},
                                                   string='Líneas de cheques externos')


class DepositLineCash(models.Model):
    _name = 'account.deposit.line.cash'
    _rec_name = 'account_id'

    _description = _('Lineas de depósito directo')

    account_id = fields.Many2one('account.account', 'Cuenta', domain=[('internal_type', '!=', 'view')], required=True)
    reference = fields.Char('Referencia')
    amount = fields.Float('Monto', required=True)
    payment_id = fields.Many2one('account.payment', string="Depósito", ondelete="cascade")


class DepositLineExternalChecks(models.Model):
    _name = 'account.deposit.line.external.checks'
    _rec_name = 'bank_id'

    _description = _('Lineas de depósito de cheuqes externos')

    bank_id = fields.Many2one('res.bank', string='Banco', required=True)
    check_account = fields.Char('No. Cuenta', required=True)
    check_number = fields.Char('No. Cheque', required=True)
    drawer = fields.Char('Girador', required=True)
    account_id = fields.Many2one('account.account', 'Cuenta', domain=[('internal_type', '!=', 'view')], required=True)
    amount = fields.Float('Monto', required=True)
    payment_id = fields.Many2one('account.payment', string="Depósito", ondelete="cascade")
