# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountRegisterPayOrder(models.TransientModel):
    _name = "eliterp.account.register.pay.order"
    _description = "Registrar orden de pago desde varias facturas"

    invoice_ids = fields.Many2many('account.invoice', string='Facturas', copy=False)
    date = fields.Date('Fecha', required=True, default=fields.Date.context_today)
    amount = fields.Float(string='Total de pago', required=True)
    comment = fields.Text('Notas y comentarios')

    @api.model
    def _compute_amount(self, invoice_ids):
        total = 0
        for inv in invoice_ids:
            total += inv.residual_pay_order
        return total

    @api.model
    def default_get(self, fields):
        rec = super(AccountRegisterPayOrder, self).default_get(fields)
        active_ids = self._context.get('active_ids')
        if not active_ids:
            raise UserError("Soló se puede generar está acción seleccionando varias facturas.")
        invoices = self.env['account.invoice'].browse(active_ids)
        if len(invoices) <= 1:
            raise UserError("No se puede generar está acción para una sola factura.")
        if any(invoice.state != 'open' for invoice in invoices):
            raise UserError("Soló se puede generar orden de pago de facturas por pagar.")
        # Revisar empresas y cuentas de facturas
        if any(inv.partner_id != invoices[0].partner_id for inv in invoices):
            raise UserError("Soló se puede generar orden de pago de facturas del mismo proveedor.")
        if any(inv.account_id != invoices[0].account_id  for inv in invoices):
            raise UserError("Soló se puede generar orden de pago de facturas con la misma cuenta por pagar.")
        total_amount = self._compute_amount(invoices)
        rec.update({
            'amount': abs(total_amount),
            'invoice_ids': [(6, 0, invoices.ids)],
        })
        return rec

    @api.multi
    def create_pay_order(self):
        # Generamos orden de pago relacionando varias facturas
        object_pay_order = self.env['eliterp.pay.order']
        name = self.env['ir.sequence'].next_by_code('pay.order')
        vals = {
            'name': name,
            'amount': self.amount,
            'date': self.date,
            'type': 'fap',
            'origin': ', '.join(str(i.number) for i in self.invoice_ids),
            'beneficiary': self.invoice_ids[0].partner_id.name,
            'comment': self.comment
        }
        pay_order = object_pay_order.create(vals)
        pay_order.update({'invoice_ids': [(6, 0, self.invoice_ids.ids)]})
