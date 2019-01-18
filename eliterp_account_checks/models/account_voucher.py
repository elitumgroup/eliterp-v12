# -*- coding: utf-8 -*-


from odoo import fields, models, api


class CollectionLine(models.Model):
    _inherit = "account.collection.line"

    @api.onchange('type_payment')
    def _onchange_type_payment(self):
        """
        Colocamos por defecto el girador el nombre del cliente
        :return:
        """
        if self.type_payment == 'check':
            self.drawer = self.voucher_id.partner_id.name

    type_payment = fields.Selection(selection_add=[('check', 'Cheque')])
    bank_id = fields.Many2one('res.bank', 'Banco de cliente')
    account_number = fields.Char('No. Cuenta')
    check_number = fields.Char('No. Cheque')
    drawer = fields.Char('Girador')
    check_type = fields.Selection([('current', 'Corriente'), ('to_date', 'A la fecha')], string='Tipo de cheque'
                                  , default='current')


class PayOrder(models.Model):
    _inherit = 'account.pay.order'

    type_egress = fields.Selection(selection_add=[('check', 'Cheque')])


class Voucher(models.Model):
    _inherit = "account.voucher"

    def _create_move_sale(self, move_id):
        """
        ME: Creamos cheques recaudados
        :return:
        """
        result = super(Voucher, self)._create_move_sale(move_id)
        object_check = self.env['account.checks']
        for check in self.collection_line.filtered(lambda x: x.type_payment == 'check'):
            object_check.create({
                'partner_id': self.partner_id.id,
                'name': check.check_number.zfill(6),
                'recipient': check.drawer,
                'type': 'receipts',
                'date': check.date_issue,
                'check_date': check.date_due,
                'bank_id': check.bank_id.id,
                'account_number': check.account_number,
                'account_id': check.account_id.id,
                'check_type': check.check_type,
                'state': 'received',
                'amount': check.amount,
                'voucher_id': self.id
            })
        return result

    @api.one
    def _create_check(self):
        """
        Función para crear cheque desde voucher
        :return:
        """
        vals = {}
        object_check = self.env['account.checks']
        vals['name'] = self.check_number
        vals['voucher_id'] = self.id
        vals['partner_id'] = self.partner_id.id if self.partner_id else False
        vals['recipient'] = self.beneficiary
        vals['type'] = 'issued'
        vals['date'] = self.date
        vals['check_date'] = self.bank_date
        vals['state'] = 'issued'
        vals['amount'] = self.amount_cancel
        object_check.create(vals)

    @api.multi
    def post_voucher(self):
        """
        ME: Creamos el cheque si el tipo de egreso es cheque y es pago
        :return:
        """
        result = super(Voucher, self).post_voucher()
        if self.voucher_type == 'purchase':
            if self.type_egress == 'check':
                self._create_check()
                new_ref = self.move_id.ref + " - Cheque: " + self.check_number
                self.move_id.update({'ref': new_ref})
        return result

    @api.onchange('check_number')
    def _onchange_check_number(self):
        """
        TODO: Rellenamos con 0 el número de cheque, pendiente hacerlo secuencial
        :return:
        """
        if self.check_number:
            number = self.bank_journal_id.check_padding
            self.check_number = self.check_number.zfill(number)

    type_egress = fields.Selection(selection_add=[('check', 'Cheque')])
    check_number = fields.Char('No. Cheque', readonly=True, states={'draft': [('readonly', False)]},
                               track_visibility='onchange')
