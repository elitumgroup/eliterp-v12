# -*- coding: utf-8 -*-


from odoo import api, models


class Payment(models.Model):
    _inherit = "account.payment"

    @api.multi
    def print_bank_records(self):
        """
        Imprimir depósito/transferencia bancaria
        :return:
        """
        self.ensure_one()
        self.env.ref('eliterp_account.action_bank_records').report_action(self)

    @api.model
    def _get_report_filename(self):
        """
        Nombre del archivo de reporte por tipo
        :return:
        """
        if self.payment_type == 'transfer':
            return 'Transferencia bancaria %s' % self.name
        else:
            return 'Depósito %s' % self.name
