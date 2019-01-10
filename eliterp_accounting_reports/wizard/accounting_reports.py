# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime
from odoo.tools import float_is_zero
from itertools import groupby


class GeneralLedgerReportPdf(models.AbstractModel):
    _name = 'report.eliterp_accounting_reports.report_general_ledger'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        object_account = self.env['account.account']
        if not doc.account_ids:
            base_accounts = self.env['account.account'].search([
                ('internal_type', '!=', 'view'),
                ('company_id', '=', doc.company_id.id)
            ])  # Todas las cuentas de la compañía
        else:
            base_accounts = doc.account_ids
        accounts = []
        data = []
        for record in base_accounts:
            accounts.append(record)
        accounts.sort(key=lambda x: x.code, reverse=False)  # Ordenamos de menor a mayor por código
        for account in accounts:
            lines = self.env['account.move.line'].search(
                [('account_id', '=', account.id), ('date', '>=', doc.start_date), ('date', '<=', doc.end_date)],
                order="date")  # Movimientos de la cuenta ordenamos por fecha
            beginning_balance = account._get_beginning_balance(doc.start_date)
            balance = beginning_balance
            total_debit = 0.00
            total_credit = 0.00
            data_line = []  # Líneas de movimientos de la cuenta
            for line in lines:
                total_debit = total_debit + line.debit
                total_credit = total_credit + line.credit
                type = (account.code.split("."))[0]
                amount = object_account._get_balance_nature_account(type, line.debit, line.credit)
                balance = balance + amount
                data_line.append({'name': line.move_id.name,
                                  'date': line.date,
                                  'detail': line.name,
                                  'debit': line.debit,
                                  'credit': line.credit,
                                  'balance': balance})

            total_balance = total_debit - total_credit
            if len(lines) != 0:  # Naturaleza de cuentas
                total_balance = object_account._get_balance_nature_account(type, total_debit, total_credit)
            total_balance = beginning_balance + total_balance
            if data_line or beginning_balance > 0:  # Soló si tienes líneas de movimiento o saldo inicial
                data.append({
                    'account': account.name,
                    'code': account.code,
                    'moves': data_line,
                    'total_debit': total_debit,
                    'total_credit': total_credit,
                    'total_balance': total_balance,
                    'beginning_balance': beginning_balance
                })
        return data

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'account.general.ledger.report',
            'docs': self.env['account.general.ledger.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class GeneralLedgerReport(models.TransientModel):
    _name = 'account.general.ledger.report'

    _description = _("Ventana para reporte de libro mayor")

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting_reports.action_report_general_ledger').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True)
    account_ids = fields.Many2many('account.account', string='Cuentas contable')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.user.company_id)


class FinancialSituationReportPdf(models.AbstractModel):
    _name = 'report.eliterp_accounting_reports.report_financial_situation'

    # TODO: Mejorar reporte muchas líneas en el código

    def get_saldo_resultado(self, cuenta, tipo, fecha_inicio, fecha_fin):
        '''Obtenemos el saldo del Estado de Resultados'''
        movimientos = self.env['account.move.line'].search([('account_id', '=', cuenta),
                                                            ('date', '>=', fecha_inicio),
                                                            ('date', '<=', fecha_fin)])

        credit = 0.00
        debit = 0.00
        for line in movimientos:
            credit += line.credit
            debit += line.debit
        monto = round(debit - credit, 2)
        if tipo == '5':
            if debit < credit:
                if monto > 0:
                    monto = -1 * round(debit - credit, 2)
        if tipo == '4':
            if debit < credit:
                if monto < 0:
                    monto = -1 * round(debit - credit, 2)
            if debit > credit:
                if monto > 0:
                    monto = -1 * round(debit - credit, 2)
        return monto

    def estado_resultado(self, fecha_inicio, fecha_fin):
        '''Obtener el monto dde Estado de Resultados'''
        cuentas_contables = self.env['account.account'].search([('user_type_id.name', '!=', 'odoo')], order="code")
        cuentas = []
        movimientos = []
        padre = False
        total_movimiento = 0.00
        cuentas_4 = cuentas_contables.filtered(lambda x: (x.code.split("."))[0] == '4')
        cuentas_5 = cuentas_contables.filtered(lambda x: (x.code.split("."))[0] == '5')
        total_ingresos = 0.00
        total_gastos = 0.00
        for cuenta in cuentas_4:
            if cuentas == []:
                cuentas.append({'code': self.env['account.account'].search([('code', '=', '4')])[0].code,
                                'name': 'INGRESOS',
                                'tipo': 'padre',
                                'sub_cuenta': [],
                                'monto': 0.00,
                                'cuenta': self.env['account.account'].search([('code', '=', '4')])[0],
                                'padre': padre})
            else:
                if cuenta.account_type == 'view':
                    padre = self.buscar_padre(cuenta)
                    cuentas = self.update_saldo(cuentas)
                    cuentas.append({'code': cuenta.code,
                                    'tipo': 'vista',
                                    'sub_cuenta': [],
                                    'name': cuenta.name,
                                    'monto': 0.00,
                                    'cuenta': cuenta,
                                    'padre': padre})
                else:
                    monto_movimiento = self.get_saldo_resultado(cuenta.id, '4', fecha_inicio, fecha_fin)
                    padre = self.buscar_padre(cuenta)
                    print(cuenta.code)
                    index = list(map(lambda x: x['code'], cuentas)).index(padre)
                    cuentas[index]['sub_cuenta'].append({'code': cuenta.code,
                                                         'tipo': 'movimiento',
                                                         'name': cuenta.name,
                                                         'monto': monto_movimiento})
                    cuentas[index]['monto'] = cuentas[index]['monto'] + monto_movimiento
        cuentas = self.update_saldo(cuentas)
        total_ingresos = cuentas[0]['monto']
        cuentas = []
        movimientos = []
        padre = False
        total_movimiento = 0.00
        for cuenta in cuentas_5:
            if cuentas == []:
                cuentas.append({'code': self.env['account.account'].search([('code', '=', '5')])[0].code,
                                'name': 'GASTOS',
                                'tipo': 'padre',
                                'sub_cuenta': [],
                                'monto': 0.00,
                                'cuenta': self.env['account.account'].search([('code', '=', '5')])[0],
                                'padre': padre})
            else:
                if cuenta.account_type == 'view':
                    padre = self.buscar_padre(cuenta)
                    cuentas = self.update_saldo(cuentas)
                    cuentas.append({'code': cuenta.code,
                                    'tipo': 'vista',
                                    'sub_cuenta': [],
                                    'name': cuenta.name,
                                    'monto': 0.00,
                                    'cuenta': cuenta,
                                    'padre': padre})
                else:
                    monto_movimiento = self.get_saldo_resultado(cuenta.id, '5', fecha_inicio, fecha_fin)
                    padre = self.buscar_padre(cuenta)
                    print(cuenta.code)
                    index = list(map(lambda x: x['code'], cuentas)).index(padre)
                    cuentas[index]['sub_cuenta'].append({'code': cuenta.code,
                                                         'tipo': 'movimiento',
                                                         'name': cuenta.name,
                                                         'monto': monto_movimiento})
                    cuentas[index]['monto'] = cuentas[index]['monto'] + monto_movimiento
        cuentas = self.update_saldo(cuentas)
        total_gastos = cuentas[0]['monto']
        return total_ingresos - total_gastos

    def update_saldo(self, cuentas):
        '''Actualizamos el saldo de la Cuenta Padre'''
        cuentas = cuentas[::-1]
        if len(cuentas) == 1:
            return cuentas[::-1]
        for cuenta in cuentas:
            cuenta['monto'] = 0.00
            total = 0.00
            if cuenta['sub_cuenta'] != []:
                for sub_cuenta in cuenta['sub_cuenta']:
                    total = total + sub_cuenta['monto']
                cuenta['monto'] = total
        for x in range(len(cuentas)):
            for y in range(len(cuentas)):
                if cuentas[x]['padre'] == cuentas[y]['code']:
                    cuentas[y]['monto'] = cuentas[y]['monto'] + cuentas[x]['monto']
        return cuentas[::-1]

    def get_saldo(self, cuenta, tipo, doc):
        '''Obtenemos el saldo de la cuenta y verificamos su naturaleza'''
        # MARZ
        movimientos = self.env['account.move.line'].search([('account_id', '=', cuenta.id),
                                                            ('date', '>=', doc.start_date),
                                                            ('date', '<=', doc.end_date)])
        credit = 0.00
        debit = 0.00
        if cuenta.code == '3.3.3':
            date_object = datetime.strptime(doc.end_date, "%Y-%m-%d")
            final = date_object.replace(year=date_object.year - 1)
            movimiento = self.env['account.move.line'].search([('account_id', '=', cuenta.id),
                                                               ('date', '=', str(final))])
            movimientos = movimientos | movimiento
        for line in movimientos:
            credit += line.credit
            debit += line.debit
        monto = round(debit - credit, 2)
        if tipo == '1':
            if debit < credit:
                if monto > 0:
                    monto = -1 * round(debit - credit, 2)
        if tipo in ('2', '3'):
            if debit < credit:
                if monto < 0:
                    monto = -1 * round(debit - credit, 2)
            if debit > credit:
                if monto > 0:
                    monto = -1 * round(debit - credit, 2)
        # Saldo Inicial de la cuenta
        if cuenta.code != '3.3.3':
            monto = monto + self.env['eliterp.accounting.help']._get_beginning_balance(cuenta, doc.start_date,
                                                                                       doc.end_date)
        return monto

    def buscar_padre(self, cuenta):
        '''Buscamos la cuenta padre de la cuenta'''
        split = cuenta.code.split(".")[:len(cuenta.code.split(".")) - 1]
        codigo = ""
        for code in split:
            if codigo == "":
                codigo = codigo + str(code)
            else:
                codigo = codigo + "." + str(code)
        return codigo

    def _get_report(self, tipo, doc):
        '''Reporte General'''
        cuentas_contables = self.env['account.account'].search([('user_type_id.name', '!=', 'odoo')], order="code")
        cuentas = []
        movimientos = []
        padre = False
        total_movimiento = 0.00
        for cuenta in cuentas_contables:
            if (cuenta.code.split("."))[0] == tipo:
                if cuentas == []:
                    # Cuentas Principales (Sin Movimiento)
                    if tipo == '1':
                        name = "ACTIVOS"
                    if tipo == '2':
                        name = "PASIVOS"
                    if tipo == '3':
                        name = "PATRIMONIO NETO"
                    cuentas.append({'code': self.env['account.account'].search([('code', '=', tipo)])[0].code,
                                    'name': name,
                                    'tipo': 'padre',
                                    'sub_cuenta': [],
                                    'monto': 0.00,
                                    'cuenta': self.env['account.account'].search([('code', '=', tipo)])[0],
                                    'padre': padre})
                else:
                    if cuenta.account_type == 'view':
                        # Cuentas Vistas
                        padre = self.buscar_padre(cuenta)
                        cuentas = self.update_saldo(cuentas)
                        cuentas.append({'code': cuenta.code,
                                        'tipo': 'vista',
                                        'sub_cuenta': [],
                                        'name': cuenta.name,
                                        'monto': 0.00,
                                        'cuenta': cuenta,
                                        'padre': padre})
                    else:
                        # Cuentas con Movimientos
                        conciliacion_bancaria = []
                        if cuenta.user_type_id.type == 'bank':
                            conciliacion_bancaria = self.env['eliterp.bank.conciliation'].search(
                                [('start_date', '=', doc.start_date),
                                 ('end_date', '=', doc.end_date),
                                 ('account_id', '=', cuenta.id)])
                            if len(conciliacion_bancaria) != 0:
                                monto_movimiento = conciliacion_bancaria[0].total
                            else:
                                monto_movimiento = self.get_saldo(cuenta, tipo, doc)
                        else:
                            monto_movimiento = self.get_saldo(cuenta, tipo, doc)
                        padre = self.buscar_padre(cuenta)
                        if cuenta.code:  # Imprimimos Cuentas (tipo = movimiento)
                            print(cuenta.code)
                        index = list(map(lambda x: x['code'], cuentas)).index(padre)
                        cuentas[index]['sub_cuenta'].append({'code': cuenta.code,
                                                             'tipo': 'movimiento',
                                                             'name': cuenta.name,
                                                             'monto': round(monto_movimiento, 2)})
                        cuentas[index]['monto'] = cuentas[index]['monto'] + monto_movimiento
            cuentas = self.update_saldo(cuentas)
        if tipo == '1':
            TOTALES.append({'total_activo': cuentas[0]['monto']})
        if tipo == '2':
            TOTALES.append({'total_pasivo': cuentas[0]['monto']})
        if tipo == '3':
            movimientos = []
            cuenta_estado = list(filter(lambda x: x['code'] == '3.3', cuentas))
            if cuenta_estado:
                if cuenta_estado[0]['monto'] != 0.00:
                    # MARZ
                    monto = self.estado_resultado(doc.start_date, doc.end_date)
                    movimientos_internos = {}
                    if monto >= 0:
                        movimientos_internos['code'] = '3.3.1.1'
                        movimientos_internos['tipo'] = 'movimiento'
                        movimientos_internos['name'] = 'GANANCIA NETA DEL PERIODO'
                        movimientos_internos['monto'] = monto
                    else:
                        movimientos_internos['code'] = '3.3.2.1'
                        movimientos_internos['tipo'] = 'movimiento'
                        movimientos_internos['name'] = '(-) PERDIDA NETA DEL PERIODO'
                        movimientos_internos['monto'] = monto
                    for cuenta in cuentas:
                        if cuenta['code'] == '3.3':
                            cuenta['sub_cuenta'].append(movimientos_internos)
                    TOTALES.append({'total_patrimonio': cuentas[0]['monto'] + monto})
                    return cuentas
            # Si Estado de Resultados es igual a 0
            monto = self.estado_resultado(doc.start_date, doc.end_date)
            if monto >= 0:
                movimientos.append({'code': '3.3.1.1',
                                    'tipo': 'movimiento',
                                    'name': 'GANANCIA NETA DEL PERIODO',
                                    'monto': monto})
            else:
                movimientos.append({'code': '3.3.2.1',
                                    'tipo': 'movimiento',
                                    'name': '(-) PERDIDA NETA DEL PERIODO',
                                    'monto': monto})
            cuentas.append({'code': '3.3',
                            'tipo': 'vista',
                            'sub_cuenta': movimientos,
                            'name': 'RESULTADO DEL EJERCICIO',
                            'monto': monto,
                            'cuenta': False,
                            'padre': False})
            cuentas[0]['monto'] = cuentas[0]['monto'] + monto
            TOTALES.append({'total_patrimonio': cuentas[0]['monto']})
        return cuentas

    def get_total_activo(self):
        return TOTALES[0]['total_activo']

    def get_total_pasivo(self):
        return TOTALES[1]['total_pasivo']

    def get_total_patrimonio(self):
        return TOTALES[2]['total_patrimonio']

    def get_total_ejercicio(self):
        return TOTALES[1]['total_pasivo'] + TOTALES[2]['total_patrimonio']

    def get_periodo(self, fecha):
        return (fecha.split("-"))[0]

    def get_cuentas_orden(self, lista):
        lista_ordenada = sorted(lista, key=lambda k: int(k['code'].replace('.', '')))
        return lista_ordenada

    @api.model
    def _get_report_values(self, docids, data=None):
        global TOTALES
        TOTALES = []
        return {
            'doc_ids': docids,
            'doc_model': 'account.financial.situation',
            'docs': self.env['account.financial.situation'].browse(docids),
            'data': data,
            'get_report': self._get_report,
            'get_total_activo': self.get_total_activo,
            'get_total_pasivo': self.get_total_pasivo,
            'get_total_patrimonio': self.get_total_patrimonio,
            'get_total_ejercicio': self.get_total_ejercicio,
            'get_periodo': self.get_periodo,
            'get_cuentas_orden': self.get_cuentas_orden,
        }


class FinancialSituationReport(models.TransientModel):
    _name = 'account.financial.situation'

    _description = _("Ventana para estado de situación financiera")

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting_reports.action_report_financial_situation').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True)
    # Análisis de gastos
    company_division_id = fields.Many2one('account.company.division', string='División', required=True)
    project_id = fields.Many2one('account.project', string='Proyecto')
    account_analytic_id = fields.Many2one('account.analytic.account', 'Centro de costo')
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.user.company_id)
