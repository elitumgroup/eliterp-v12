# -*- coding: utf-8 -*-

from odoo import fields, models, _


class Category(models.Model):
    _inherit = 'product.category'

    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.user.company_id)
