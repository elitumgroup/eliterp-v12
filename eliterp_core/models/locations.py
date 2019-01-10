# -*- coding: utf-8 -*-

from odoo import models, fields, _


class State(models.Model):
    _inherit = "res.country.state"

    _order = 'name asc'


class Canton(models.Model):
    _name = 'canton'
    _description = _("Cantón")

    _order = "name asc"

    state_id = fields.Many2one('res.country.state', string='Provincia', required=True, ondelete='cascade')
    name = fields.Char('Nombre', required=True, index=True)
    code = fields.Char('Código', size=4, required=True)

    _sql_constraints = [
        ('code_unique', 'unique (code)', _("El código debe ser único."))
    ]


class Parish(models.Model):
    _name = 'parish'
    _description = _("Parroquia")

    _order = "name asc"

    canton_id = fields.Many2one('canton', string='Cantón', required=True, ondelete='cascade')
    name = fields.Char('Nombre', required=True, index=True)
    code = fields.Char('Código', size=6, required=True)

    _sql_constraints = [
        ('code_unique', 'unique (code)', _("El código debe ser único."))
    ]
