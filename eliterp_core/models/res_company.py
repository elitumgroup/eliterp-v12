# -*- coding: utf-8 -*-

from odoo import models, fields


class Company(models.Model):
    _inherit = 'res.company'

    report_color = fields.Char(string="Color de reportes", help="Seleccionar color para las líneas de reporte.")
