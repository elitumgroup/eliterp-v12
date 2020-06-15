# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class Voucher(models.Model):
    _inherit = "account.voucher"

    @api.multi
    def print_voucher(self):
        self.ensure_one()
        if self.voucher_type == 'sale':
            report = self.env.ref('eliterp_treasury.action_report_voucher_sale')
        else:
            report = self.env.ref('eliterp_treasury.action_report_voucher')
        return report.report_action(self)

    @api.model
    def _get_report_filename(self):
        """
        Nombre del archivo de reporte por tipo de voucher
        :return:
        """
        if self.voucher_type == 'purchase':
            return 'Pago %s' % self.name
        else:
            return 'Cobro %s' % self.name
