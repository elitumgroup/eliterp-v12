# -*- coding: utf-8 -*-

from odoo import models, api


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def setting_chart_of_accounts_action(self):
        """
        ME: Añadimos al dominio tipos de cuentas diferentes a las de vista
        :return:
        """
        res = super(ResCompany, self).setting_chart_of_accounts_action()
        res['domain'].append(('internal_type', '!=', 'view'))
        return res
