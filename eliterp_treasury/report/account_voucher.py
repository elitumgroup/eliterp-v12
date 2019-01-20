# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class Voucher(models.Model):
    _inherit = "account.voucher"

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
