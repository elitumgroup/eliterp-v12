# -*- coding: utf-8 -*-


from odoo import fields, models, api, _
from datetime import date


class DepositLineCollectedcheck(models.Model):
    _name = 'account.deposit.line.collected.check'

    _description = _('Lineas de depósito de cheques recaudados')

    name = fields.Many2one('account.checks', string="Cheque", required=True)
    amount = fields.Float('Monto', related='name.amount', store=True, readonly=True)
    bank_id = fields.Many2one('res.bank', related='name.bank_id', readonly=True)
    check_date = fields.Date('Fecha de cheque', related='name.check_date', readonly=True)
    account_id = fields.Many2one('account.account', related='name.account_id', readonly=True,
                                 string='Cuenta de recaudo')
    payment_id = fields.Many2one('account.payment', string="Depósito", ondelete="cascade")


class Payment(models.Model):
    _inherit = "account.payment"

    @api.multi
    def load_checks(self):
        """
        Cargamos cheques por compañía mayores a la fecha actual y menores a la fecha del cheque
        :return:
        """
        self.deposit_line_checks_collected.unlink()  # Borramos líneas anteriores
        today = date.today().strftime('%Y-%m-%d')
        checks = self.env['account.checks'].search([
            ('date', '<=', today),
            ('check_date', '>=', today),
            ('company_id', '=', self.company_id.id),
            ('type', '=', 'receipts'),
            ('state', '=', 'received')
        ])
        lines = []
        for check in checks:
            lines.append([0, 0, {'name': check.id}])
        return self.update({'deposit_line_checks_collected': lines})

    def _get_move_lines(self, move_line=None, move_id=None):
        """
        Creamos líneas de movimiento contable dependiendo del tipo de depósito
        :return:
        """
        if self.type_deposit == 'checks_collected':
            for line in self.deposit_line_checks_collected:
                move_line.create({
                    'name': "%s: %s" % (line.bank_id.name, line.name),
                    'journal_id': move_id.journal_id.id,
                    'account_id': line.account_id.id,
                    'move_id': move_id.id,
                    'debit': 0.0,
                    'credit': line.amount,
                    'date': self.payment_date,
                })
        return super(Payment, self)._get_move_lines(move_line=move_line, move_id=move_id)

    @api.multi
    def post_deposit(self):
        """
        Ponemos como depositados los cheques validados
        :return:
        """
        for check in self.deposit_line_checks_collected:
            check.name.update({'state': 'deposited'})
        return super(Payment, self).post_deposit()

    def _get_amount(self):
        """
        Sumar monto de cada línea de cheques
        :return:
        """
        res = super(Payment, self)._get_amount()
        if self.type_deposit == 'checks_collected':
            total = 0.00
            for line in self.deposit_line_checks_collected:
                total += line.amount
            return total
        return res

    type_deposit = fields.Selection(selection_add=[('checks_collected', 'Cheques recaudados')])
    deposit_line_checks_collected = fields.One2many('account.deposit.line.collected.check', 'payment_id', readonly=True,
                                                    states={'draft': [('readonly', False)]},
                                                    string='Líneas de cheques recaudados')


class BankRecordsCancel(models.TransientModel):
    _inherit = 'account.bank.records.cancel'

    @api.multi
    def confirm_cancel(self):
        """
        Cambiamos los estados de los cheques si es depósito (Los regresamos a recibidos)
        :return:
        """
        result =  super(BankRecordsCancel, self).confirm_cancel()
        if self.record_id.type_deposit == 'checks_collected':
            for check in self.record_id.deposit_line_checks_collected:
                check.name.update({'state': 'received'})
        return result
