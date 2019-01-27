# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero


class Requirement(models.Model):
    _inherit = 'payment.requirement'

    @api.multi
    def print_requirement(self):
        """
        Imprimimos requerimiento de pago
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_payment_requirement.action_report_payment_requirement').report_action(self)
