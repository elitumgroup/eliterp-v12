# -*- coding: utf-8 -*-


from odoo import fields, models, _


class Bank(models.Model):
    _inherit = 'res.bank'

    state_id = fields.Many2one("res.country.state", string='Provincia', required=True)
    bic = fields.Char('Bank Identifier Code', index=True, help="Sometimes called BIC or Swift.", required=True) # CM

    _sql_constraints = [
        ('unique_bic', 'unique(country,bic)', _("El código de banco es único por país!")),
    ]
