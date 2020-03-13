# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero


class MoveLine(models.Model):
    _inherit = 'account.move.line'

    my_reconcile = fields.Boolean('Conciliado', defualt=False)


class Voucher(models.Model):
    _inherit = 'account.voucher'

    reconcile = fields.Boolean('Conciliado?', default=False, track_visibility='onchange')


class Voucher(models.Model):
    _inherit = 'account.checks'

    reconcile = fields.Boolean(related='voucher_id.reconcile', string='Conciliado?', store=True)


class BankReconciliationLine(models.Model):
    _name = 'account.bank.reconciliation.line'

    _description = _('Línea de conciliación bancaria')
    _order = "date asc"

    @api.depends('move_line_id')
    def _compute_amount(self):
        """
        Calculamos el signo de la línea de movimiento
        :return:
        """
        for record in self:
            amount = 0.00
            move = record.move_line_id
            if float_is_zero(move.credit, 0.01):
                amount = abs(move.debit)
            if float_is_zero(move.debit, 0.01):
                amount = -1 * abs(move.credit)
            record.amount = amount

    check = fields.Boolean(default=False, string="Seleccionar?")
    move_line_id = fields.Many2one('account.move.line', string='Movimiento contable', required=True)
    date = fields.Date(related='move_line_id.date', string="Fecha", store=True)
    journal = fields.Many2one('account.journal', related='move_line_id.journal_id', string="Diario contable",
                              store=True)
    concept = fields.Char(related='move_line_id.name', string="Concepto", store=True)
    name = fields.Char(related='move_line_id.ref', string="Referencia", store=True)
    amount = fields.Float('Monto', compute='_compute_amount', store=True)
    reconciliation_id = fields.Many2one('account.bank.reconciliation', ondelete='cascade',
                                        string="Conciliación bancaria")


class BankReconciliation(models.Model):
    _name = 'account.bank.reconciliation'
    _inherit = ['mail.thread']

    _description = _("Conciliación bancaria")
    _order = "journal_id asc, date_to desc"

    @api.one
    @api.depends('bank_reconciliation_line.check', 'beginning_balance')
    def _compute_amount(self):
        """
        Calculamos el saldo bancario y saldo contable
        """
        countable_balance = 0.00
        account_balance = 0.00
        if not self.bank_reconciliation_line:
            self.countable_balance = countable_balance
            self.account_balance = self.beginning_balance
        else:
            for line in self.bank_reconciliation_line:
                if line.check:
                    account_balance += line.amount
                countable_balance += line.amount
            self.countable_balance = countable_balance + self.beginning_balance
        self.account_balance = self.beginning_balance + account_balance

    def _get_bank_reconciliation(self, journal_id):
        reconciliation_ids = self.search([
            ('state', '=', 'posted'),
            ('journal_id', '=', journal_id.id)
        ])
        return reconciliation_ids

    @api.multi
    def load_moves(self):
        """
        Cargamos líneas de movimiento del banco
        :return:
        """
        self.ensure_one()
        account = self.journal_id.default_debit_account_id
        moves = self.env['account.move.line'].search([
            ('account_id', '=', account.id),
            ('my_reconcile', '=', False),
            ('date', '<=', self.date_to)
        ])
        move_lines = [(2, line.id, False) for line in self.bank_reconciliation_line]
        reconciliation_ids = self._get_bank_reconciliation(self.journal_id)
        # Saldo inicial de cuenta contable si no existe conciliación alguna previa
        # caso contrario se coje los datos de la última conciliación validada
        if not reconciliation_ids:
            beginning_balance = account._get_beginning_balance(self.date_from)
        else:
            reconciliation = reconciliation_ids[0]
            beginning_balance = reconciliation.account_balance
        for line in moves:
            if line.move_id.state == 'posted' and not line.move_id.reversed:
                move_lines.append([0, False, {'move_line_id': line.id}])
        self.write({
            'beginning_balance': beginning_balance,
            'bank_reconciliation_line': move_lines

        })
        return True

    def _get_name(self):
        company = self.company_id
        sequence = self.env['ir.sequence'].with_context(force_company=company.id).next_by_code('bank.reconciliation')
        if not sequence:
            raise UserError(
                _("No está definida la secuencia con código 'bank.reconciliation' para compañía: %s") % company.name)
        return sequence

    @api.multi
    def posted_conciliation(self):
        """
        Confirmamos la conciliación bancaria
        :return:
        """
        self._set_reconcile()
        new_name = self._get_name()
        return self.write({
            'state': 'posted',
            'name': new_name
        })

    def _set_reconcile(self):
        """
        Colocamos cómo conciliados los cheques del voucher seleccionados
        :return:
        """
        for line in self.bank_reconciliation_line.filtered(
                lambda x: x.journal.name == 'Comprobante de egreso' and x.check):
            move = line.move_line_id.move_id
            voucher = self.env['account.voucher'].search([
                ('move_id', '=', move.id)
            ])
            voucher.update({'reconcile': True})

    def _remove_reconcile(self):
        """
        Colocamos cómo no conciliados los documentos seleccionados al cancelar
        :return:
        """
        for line in self.bank_reconciliation_line.filtered(
                lambda x: x.journal.name == 'Comprobante de egreso' and x.check):
            move = line.move_line_id.move_id
            voucher = self.env['account.voucher'].search([
                ('move_id', '=', move.id)
            ])
            voucher.update({'reconcile': False})

    @api.multi
    def action_button_cancel(self):
        """
        Cancelamos la conciliación y quitamos el check de cheques en vouchers
        :return:
        """
        self._remove_reconcile()
        return self.write({
            'state': 'cancel'
        })

    @api.multi
    def unlink(self):
        for record in self:
            if not record.state == 'draft':
                raise UserError("No se puede borrar una conciliación diferente de borrador.")
        return super(BankReconciliation, self).unlink()

    name = fields.Char('No. Documento', index=True)
    concept = fields.Char('Concepto', readonly=True, states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.user.company_id)
    journal_id = fields.Many2one('account.journal', 'Banco', required=True, readonly=True,
                                 states={'draft': [('readonly', False)]}, track_visibility='onchange')
    bank_reconciliation_line = fields.One2many('account.bank.reconciliation.line', 'reconciliation_id',
                                               string='Líneas de conciliación bancaria', readonly=True,
                                               states={'draft': [('readonly', False)]})
    date_from = fields.Date('Fecha inicio', required=True, track_visibility='onchange', readonly=True,
                            states={'draft': [('readonly', False)]})
    date_to = fields.Date('Fecha fin', required=True, track_visibility='onchange', readonly=True,
                          states={'draft': [('readonly', False)]})
    beginning_balance = fields.Float('Saldo inicial', required=True, readonly=True,
                                     states={'draft': [('readonly', False)]})
    countable_balance = fields.Float('Saldo contable', compute='_compute_amount', store=True)
    account_balance = fields.Float('Saldo bancario', compute='_compute_amount', store=True)
    state = fields.Selection([('draft', 'Borrador'), ('posted', 'Validada'), ('cancel', 'Anulada')], string="Estado",
                             default='draft')
    notes = fields.Text('Notas', readonly=True, states={'draft': [('readonly', False)]})
    comment = fields.Text(string='Notas adicionales')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('posted', 'Validada'),
        ('cancel', 'Anulado')
    ], readonly=True, default='draft', copy=False, string="Estado", track_visibility='onchange')
