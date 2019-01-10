# -*- coding: utf-8 -*-

from odoo import fields, models


class ConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_wage = fields.Float(
        'Sueldo básico unficado',
        default_model='hr.contract',
        default=394
    )
    default_test_days = fields.Integer(
        'Días de período de prueba',
        default_model='hr.contract',
        default=90
    )
