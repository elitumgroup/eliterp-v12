# -*- coding: utf-8 -*-

from odoo import api, fields, models


class Order(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def _prepare_invoice(self):
        """
        ME: Extendemos el método par añadir el punto de impresión y autorización
        # TODO: Revisar está opción
        :return:
        """
        self.ensure_one()
        invoice_vals = super(Order, self)._prepare_invoice()
        invoice_vals['point_printing_id'] = self.point_printing_id.id
        return invoice_vals

    @api.model
    def _default_point_printing(self):
        """
        Defecto de punto de impresión
        :return:
        """
        company = self.env.user.company_id.id
        point_printing_ids = self.env['sri.point.printing'].search([('company_id', '=', company)], limit=1)
        return point_printing_ids

    point_printing_id = fields.Many2one('sri.point.printing', string='Punto de impresión', readonly=True,
                                        default=_default_point_printing,
                                        states={'draft': [('readonly', False)]})
