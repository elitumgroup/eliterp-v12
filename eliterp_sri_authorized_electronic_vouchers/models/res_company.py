# -*- coding: utf-8 -*-

from odoo import fields, models


class Partner(models.Model):
    _inherit = 'res.partner'

    email_optional = fields.Char('Correo electrónico opcional')


class Company(models.Model):
    _inherit = 'res.company'

    electronic_signature = fields.Binary('Firma electrónica', attachment=True, copy=False, required=True)
    electronic_signature_name = fields.Char('Nombre de firma electrónica', copy=False)
    password_electronic_signature = fields.Char(
        'Clave para firma electrónica',
        size=255,
    )
    # Off-line no necesita ('2', 'Indisponibilidad')
    type_emission = fields.Selection(
        [
            ('1', 'Normal')
        ],
        string='Tipo de emisión',
        required=True,
        default='1'
    )
    environment = fields.Selection(
        [
            ('1', 'Pruebas'),
            ('2', 'Producción')
        ],
        string='Entorno',
        required=True,
        default='1'
    )
    contingency_key_ids = fields.One2many(
        'sri.contingency.keys',
        'company_id',
        string='Claves de contingencia'
    )


class ContingencyKeys(models.Model):
    _name = 'sri.contingency.keys'
    _description = 'Claves de contigencia'

    name = fields.Char('Clave', size=37, required=True)
    used = fields.Boolean('Usada?', readonly=True)
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        ondelete="cascade"
    )

    _sql_constraints = [
        (
            'key_unique',
            'unique(name, company_id)',
            "Clave de contingencia debe ser única por compañia!"
        )
    ]
