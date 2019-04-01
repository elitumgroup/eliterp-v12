# -*- coding: utf-8 -*-).

from odoo import models, tools, _
import babel
from datetime import datetime, timedelta
import time
import math

UNIDADES = (
    '', 'Un ', 'Dos ', 'Tres ', 'Cuatro ', 'Cinco ', 'Seis ', 'Siete ', 'Ocho ', 'Nueve ', 'Diez ', 'Once ',
    'Doce ',
    'Trece ', 'Catorce ', 'Quince ', 'Dieciséis ', 'Diecisiete ', 'Dieciocho ', 'Diecinueve ', 'Veinte ')
DECENAS = ('Veinti', 'Treinta ', 'Cuarenta ', 'Cincuenta ', 'Sesenta ', 'Setenta ', 'Ochenta ', 'Noventa ', 'Cien ')
CENTENAS = (
    'Ciento ', 'Doscientos ', 'Trescientos ', 'Cuatrocientos ', 'Quinientos ', 'Seiscientos ', 'Setecientos ',
    'Ochocientos ', 'Novecientos ')


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

    def __convertNumber(self, n):
        output = ''
        if (n == '100'):
            output = "Cien "
        elif (n[0] != '0'):
            output = CENTENAS[int(n[0]) - 1]
        k = int(n[1:])
        if (k <= 20):
            output += UNIDADES[k]
        else:
            if ((k > 30) & (n[2] != '0')):
                output += '%sy %s' % (DECENAS[int(n[1]) - 2], UNIDADES[int(n[2])])
            else:
                output += '%s%s' % (DECENAS[int(n[1]) - 2], UNIDADES[int(n[2])])
        return output

    def Numero_a_Texto(self, number_in):
        convertido = ''
        number_str = str(number_in) if (type(number_in) != 'str') else number_in
        number_str = number_str.zfill(9)
        millones, miles, cientos = number_str[:3], number_str[3:6], number_str[6:]
        if (millones):
            if (millones == '001'):
                convertido += 'Un Millon '
            elif (int(millones) > 0):
                convertido += '%sMillones ' % self.__convertNumber(millones)
        if (miles):
            if (miles == '001'):
                convertido += 'Mil '
            elif (int(miles) > 0):
                convertido += '%sMil ' % self.__convertNumber(miles)
        if (cientos):
            if (cientos == '001'):
                convertido += 'Un '
            elif (int(cientos) > 0):
                convertido += '%s ' % self.__convertNumber(cientos)
        return convertido

    def get_amount_to_word(self, j):
        try:
            Arreglo1 = str(j).split(',')
            Arreglo2 = str(j).split('.')
            if (len(Arreglo1) > len(Arreglo2) or len(Arreglo1) == len(Arreglo2)):
                Arreglo = Arreglo1
            else:
                Arreglo = Arreglo2

            if (len(Arreglo) == 2):
                whole = math.floor(j)
                frac = j - whole
                num = str("{0:.2f}".format(frac))[2:]
                return (self.Numero_a_Texto(Arreglo[0]) + 'con ' + num + "/100").capitalize()
            elif (len(Arreglo) == 1):
                return (self.Numero_a_Texto(Arreglo[0]) + 'con ' + '00/100').capitalize()
        except ValueError:
            return "Cero"

    @staticmethod
    def _get_month_name(month):
        if month == 1:
            return "Enero"
        if month == 2:
            return "Febrero"
        if month == 3:
            return "Marzo"
        if month == 4:
            return "Abril"
        if month == 5:
            return "Mayo"
        if month == 6:
            return "Junio"
        if month == 7:
            return "Julio"
        if month == 8:
            return "Agosto"
        if month == 9:
            return "Septiembre"
        if month == 10:
            return "Octubre"
        if month == 11:
            return "Noviembre"
        if month == 12:
            return "Diciembre"

    def _get_date_format_contract(self, date):
        month = self._get_month_name(int(date.month))
        return '%s de %s del %s' % (date.day, month, date.year)

    def get_date_format_invoice1(self, date):
        month = self._get_month_name(int(date.month))
        return '%s días del mes de %s del año %s' % (date.day, month, date.year)
