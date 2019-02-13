# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class ConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_expenses_pay = fields.Many2one('account.account',
                                           'Cuenta para pago de viáticos (Con solicitud)',
                                           default_model='account.voucher',
                                           domain=[('account_type', '=', 'movement')]
                                           )
