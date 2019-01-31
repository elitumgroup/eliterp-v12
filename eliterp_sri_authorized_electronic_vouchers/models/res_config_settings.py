# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    response_time_sri = fields.Integer('Tiempo de respuesta SRI', default=3,
                                       help="Campo para tiempo máximo de autorización del SRI.")
