# -*- coding: utf-8 -*-

from odoo import fields, models, _


class Company(models.Model):
    _inherit = 'res.company'

    special_contributor = fields.Boolean('Es contribuyente especial?', default=False)
    code_special_contributor = fields.Char('Código de contribuyente especial')
    authorization_ids = fields.One2many(
        'sri.authorization',
        'company_id',
        string='Autorizaciones SRI'
    )
