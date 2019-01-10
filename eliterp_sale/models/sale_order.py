# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Order(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def _prepare_invoice(self):
        """
        ME: Extendemos el método par añadir otros datos
        :return:
        """
        self.ensure_one()
        invoice_vals = super(Order, self)._prepare_invoice()
        invoice_vals['company_division_id'] = self.company_division_id.id
        invoice_vals['project_id'] = self.project_id.id
        return invoice_vals

    company_division_id = fields.Many2one('account.company.division', string='División', readonly=True,
                                          states={'draft': [('readonly', False)]}, track_visibility='onchange')
    project_id = fields.Many2one('account.project', string='Proyecto', readonly=True,
                                 states={'draft': [('readonly', False)]}, track_visibility='onchange')
