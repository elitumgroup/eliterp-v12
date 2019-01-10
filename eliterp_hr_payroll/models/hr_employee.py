# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime


class Employee(models.Model):
    _inherit = 'hr.employee'

    @api.depends('admission_date')
    def _compute_working_time(self):
        """
        Calculamos si empleado tiene más de 365 días de trabajo (Para benefecios sociales)
        :return:
        """
        day = 0.0328767  # Equivalencia en meses (Días exactos)
        date_to = datetime.today().date()
        for record in self:
            date_from = record.admission_date
            days = abs(date_to - date_from).days
            months = round(days * day, 0)
            if months >= 13:
                record.working_time = True

    working_time = fields.Boolean('Tiempo laboral?', compute='_compute_working_time', default=False, help="Sirve"
                                                                                                          "para saber si el empleado es merecedor de beneficios sociales (Fondos de reserva).")
    accumulate_tenths = fields.Selection([('yes', 'Si'), ('no', 'No')], string='Acumula décimos?', default='no')
    accumulate_reserve_funds = fields.Selection([('yes', 'Si'), ('no', 'No')], string='Acumula fondos de reserva?',
                                                default='no')
    # TODO: Revisar para qué no se pueda cambiar esto hasta el otro enero