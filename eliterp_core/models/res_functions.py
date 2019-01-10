# -*- coding: utf-8 -*-).

from odoo import models, tools, _
import babel
from datetime import datetime
import time


class Functions(models.AbstractModel):
    _name = 'res.functions'
    _description = _("Funciones de ayuda")

    def _get_amount_letters(self, amount):
        """
        Función para transformar cantidad a cantidad en letras
        :param amount:
        :return string:
        """
        currency = self.env.ref('base.USD')
        text = currency[0].amount_to_text(amount).replace('Dollars', 'Dólares')  # Dollars, Cents
        text = text.replace('Cents', 'Centavos')
        return text

    def _get_period_string(self, date):
        """
        Función para devolver el período tipo MMMM[y] de una fecha
        :param date:
        :return string:
        """
        ttyme = datetime.fromtimestamp(time.mktime(date.timetuple()))
        locale = self.env.context.get('lang') or 'es_EC'
        period = tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM [y]', locale=locale)).title()
        return period
