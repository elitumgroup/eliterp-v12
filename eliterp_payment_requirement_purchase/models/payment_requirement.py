# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero


class Requirement(models.Model):
    _inherit = 'payment.requirement'

    purchase_id = fields.Many2one(
        'purchase.order',
        string='Pedido de compra',
        readonly=True, states={'draft': [('readonly', False)]}
    )

    @staticmethod
    def _prepare_requirement_line_from_po(amount_total):
        data = {
            'name': 'Anticipo de Orden de Comrpa',
            'amount': amount_total
        }
        return data

    @api.onchange('purchase_id')
    def purchase_order_change(self):
        if not self.purchase_id:
            return {}
        if not self.supplier_id:
            self.supplier_id = self.purchase_id.partner_id.id
        new_lines = self.env['payment.requirement.line']
        data = self._prepare_requirement_line_from_po(self.purchase_id.amount_total)
        new_line = new_lines.new(data)
        new_lines += new_line
        self.line_ids += new_lines
        return {}
