# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime
from odoo.tools import float_is_zero
from itertools import groupby


class ReportHelpFunctions(models.AbstractModel):
    _name = 'account.report.help.functions'
    _description = _("Funciones de ayuda para reportes contables")

    @staticmethod
    def _query_parent(account):
        """
        Obtenemos el código padre
        :param account:
        :return string:
        """
        split = account.code.split(".")[:len(account.code.split(".")) - 1]
        code = ""
        for a in split:
            if code == "":
                code = code + str(a)
            else:
                code = code + "." + str(a)
        return code

    @staticmethod
    def _update_amount(accounts):
        """
        Actualizamos el monto de cuenta padre de las subcuentas dadas
        :param accounts:
        :return list:
        """
        accounts = accounts[::-1]
        if len(accounts) == 1:
            return accounts[::-1]
        for account in accounts:
            account['amount'] = 0.00
            total = 0.00
            if account['subaccounts']:
                for subaccount in account['subaccounts']:
                    total = total + subaccount['amount']
                account['amount'] = total
        for x in range(len(accounts)):
            for y in range(len(accounts)):
                if accounts[x]['parent'] == accounts[y]['code']:
                    accounts[y]['amount'] = accounts[y]['amount'] + accounts[x]['amount']
        return accounts[::-1]


class StatusResultsPdf(models.AbstractModel):
    _name = 'report.eliterp_accounting_reports.report_status_results'

    def _get_account_balance(self, account, type, context):
        """
        Obtenemos el balance de cuenta, TODO: Falta filtrar por datos de coste
        :param account:
        :param type:
        :param doc:
        :return:
        """
        beginning_balance = account._get_beginning_balance(context.start_date)
        moves = self.env['account.move.line'].search([
            ('account_id', '=', account.id),
            ('date', '>=', context.start_date),
            ('date', '<=', context.end_date)
        ])
        credit = 0.00
        debit = 0.00
        for line in moves:
            credit += line.credit
            debit += line.debit
        balance = account._get_balance_nature_account(type, debit, credit)
        return round(balance + beginning_balance, 2)

    def _get_lines(self, context, type):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        help_functions = self.env['account.report.help.functions']
        accounts = []
        accounts_base = self.env['account.account'].search([
            ('code', '=ilike', type + '%'),
            ('company_id', '=', context.company_id.id)
        ])
        for account in accounts_base:
            if not accounts:
                accounts.append({
                    'code': account.code,
                    'name': account.name,
                    'type': 'principal',
                    'subaccounts': [],
                    'amount': 0.00,
                    'account': account,
                    'parent': False
                })
            else:
                if account.internal_type == 'view':
                    parent = help_functions._query_parent(account)
                    accounts = help_functions._update_amount(accounts)
                    accounts.append({
                        'code': account.code,
                        'name': account.name,
                        'type': 'view',
                        'subaccounts': [],
                        'amount': 0.00,
                        'account': account,
                        'parent': parent
                    })
                else:
                    parent = help_functions._query_parent(account)
                    index = list(map(lambda x: x['code'], accounts)).index(parent)
                    accounts[index]['subaccounts'].append({
                        'code': account.code,
                        'type': 'movement',
                        'name': account.name,
                        'amount': self._get_account_balance(account, type, context)
                    })
                    accounts[index]['amount'] = accounts[index]['amount'] + self._get_account_balance(account, type,
                                                                                                      context)
        accounts = help_functions._update_amount(accounts)
        if type == '4':
            TOTALS.append({'total_income': accounts[0]['amount']})
        else:
            TOTALS.append({'total_spends': accounts[0]['amount']})
        return accounts

    @staticmethod
    def _get_total_exercise():
        """
        Total del ejercicio
        :return: float
        """
        return TOTALS[0]['total_income'] - TOTALS[1]['total_spends']

    @staticmethod
    def _get_result():
        """
        Si existen ganancias o pérdidas colocar estado de variable
        :return: boolean
        """
        if TOTALS[0]['total_income'] - TOTALS[1]['total_spends'] >= 0:
            return True
        else:
            return False

    @api.model
    def _get_report_values(self, docids, data=None):
        global TOTALS  # Variable para valores totales
        TOTALS = []
        return {
            'doc_ids': docids,
            'doc_model': 'account.status.results',
            'docs': self.env['account.status.results'].browse(docids),
            'get_lines': self._get_lines,
            'get_total_exercise': self._get_total_exercise,
            'get_result': self._get_result,
            'data': data,
        }


class StatusResults(models.TransientModel):
    _name = 'account.status.results'
    _description = _("Ventana para estado de resultados")

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting_reports.action_report_status_results').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True)
    # Análisis de gastos
    company_division_id = fields.Many2one('account.company.division', string='División', required=True)
    # project_id = fields.Many2one('account.project', string='Proyecto')
    # account_analytic_id = fields.Many2one('account.analytic.account', 'Centro de costo')
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.user.company_id)


class FinancialSituationPdf(models.AbstractModel):
    _name = 'report.eliterp_accounting_reports.report_financial_situation'

    # TODO: Mejorar reporte muchas líneas en el código

    def _get_status_results(self, context):
        """
        Estado de resultados en estado de situación financiera
        :param start_date:
        :param end_date:
        :return:
        """
        help_functions = self.env['account.report.help.functions']
        accounts_base = self.env['account.account'].search([('company_id', '=', context.company_id.id)], order="code")
        accounts = []
        parent = False
        accounts_4 = accounts_base.filtered(lambda x: (x.code.split("."))[0] == '4')
        accounts_5 = accounts_base.filtered(lambda x: (x.code.split("."))[0] == '5')
        for account in accounts_4:
            if not accounts:
                accounts.append({'code': self.env['account.account'].search([('code', '=', '4')])[0].code,
                                 'name': 'INGRESOS',
                                 'type': 'parent',
                                 'subaccounts': [],
                                 'amount': 0.00,
                                 'account': self.env['account.account'].search([('code', '=', '4')])[0],
                                 'parent': parent})
            else:
                if account.internal_type == 'view':
                    parent = help_functions._query_parent(account)
                    accounts = help_functions._update_amount(accounts)
                    accounts.append({'code': account.code,
                                     'type': 'view',
                                     'subaccounts': [],
                                     'name': account.name,
                                     'amount': 0.00,
                                     'account': account,
                                     'parent': parent})
                else:
                    balance_account = self.env[
                        'report.eliterp_accounting_reports.report_status_results']._get_account_balance(account,
                                                                                                           '4', context)
                    parent = help_functions._query_parent(account)
                    index = list(map(lambda x: x['code'], accounts)).index(parent)
                    accounts[index]['subaccounts'].append({'code': account.code,
                                                           'type': 'movement',
                                                           'name': account.name,
                                                           'amount': balance_account})
                    accounts[index]['amount'] = accounts[index]['amount'] + balance_account
        accounts = help_functions._update_amount(accounts)
        total_income = accounts[0]['amount']
        accounts = []
        parent = False
        for account in accounts_5:
            if accounts == []:
                accounts.append({'code': self.env['account.account'].search([('code', '=', '5')])[0].code,
                                 'name': 'GASTOS',
                                 'type': 'parent',
                                 'subaccounts': [],
                                 'amount': 0.00,
                                 'account': self.env['account.account'].search([('code', '=', '5')])[0],
                                 'parent': parent})
            else:
                if account.internal_type == 'view':
                    parent = help_functions._query_parent(account)
                    accounts = help_functions._update_amount(accounts)
                    accounts.append({'code': account.code,
                                     'type': 'view',
                                     'subaccounts': [],
                                     'name': account.name,
                                     'amount': 0.00,
                                     'account': account,
                                     'parent': parent})
                else:
                    balance_account = self.env[
                        'report.eliterp_accounting_reports.report_status_results']._get_account_balance(account,
                                                                                                           '5', context)
                    parent = help_functions._query_parent(account)
                    index = list(map(lambda x: x['code'], accounts)).index(parent)
                    accounts[index]['subaccounts'].append({'code': account.code,
                                                           'type': 'movement',
                                                           'name': account.name,
                                                           'amount': balance_account})
                    accounts[index]['amount'] = accounts[index]['amount'] + balance_account
        accounts = help_functions._update_amount(accounts)
        total_spends = accounts[0]['amount']
        return total_income - total_spends

    def _get_account_balance(self, account, type, context):
        """
        Obtenemos el saldo de la cuenta
        :param account:
        :param type:
        :param context:
        :return:
        """
        moves = self.env['account.move.line'].search([
            ('account_id', '=', account.id),
            ('date', '>=', context.start_date),
            ('date', '<=', context.end_date)
        ])
        credit = 0.00
        debit = 0.00
        if account.code == '3.3':  # TODO: Revisar para qué es esto
            final_date = context.end_date.replace(year=context.end_date.year - 1)
            move = self.env['account.move.line'].search([
                ('account_id', '=', account.id),
                ('date', '=', str(final_date))
            ])
            moves = moves | move
        for line in moves:
            credit += line.credit
            debit += line.debit
        balance = account._get_balance_nature_account(type, debit, credit)

        if account.code != '3.3':
            balance = balance + account._get_beginning_balance(context.start_date)
        return balance

    def _get_report(self, type, context):
        """
        Reporte de estado de situación financiera
        :param type:
        :param context:
        :return:
        """
        help_functions = self.env['account.report.help.functions']
        accounts_base = self.env['account.account'].search([
            ('company_id', '=', context.company_id.id)], order="code")
        accounts = []
        parent = False
        for account in accounts_base:
            if (account.code.split("."))[0] == type:
                if accounts == []:
                    # Cuentas Principales (Sin Movimiento)
                    if type == '1':
                        name = "ACTIVOS"
                    if type == '2':
                        name = "PASIVOS"
                    if type == '3':
                        name = "PATRIMONIO NETO"
                    accounts.append({'code': self.env['account.account'].search([('code', '=', type)])[0].code,
                                     'name': name,
                                     'type': 'principal',
                                     'subaccounts': [],
                                     'amount': 0.00,
                                     'account': self.env['account.account'].search([('code', '=', type)])[0],
                                     'parent': parent})
                else:
                    if account.internal_type == 'view':
                        # Cuentas vistas
                        parent = help_functions._query_parent(account)
                        accounts = help_functions._update_amount(accounts)
                        accounts.append({'code': account.code,
                                         'type': 'view',
                                         'subaccounts': [],
                                         'name': account.name,
                                         'amount': 0.00,
                                         'account': account,
                                         'parent': parent})
                    else:
                        # Cuentas movimientos
                        if account.user_type_id.type == 'bank':
                            bank_reconciliation = self.env['account.bank.reconciliation'].search(
                                [('start_date', '=', context.start_date),
                                 ('end_date', '=', context.end_date),
                                 ('account_id', '=', account.id)])
                            if not bank_reconciliation:
                                balance_account = bank_reconciliation[0].total
                            else:
                                balance_account = self._get_account_balance(account, type, context)
                        else:
                            balance_account = self._get_account_balance(account, type, context)
                        parent = help_functions._query_parent(account)
                        index = list(map(lambda x: x['code'], accounts)).index(parent)
                        accounts[index]['subaccounts'].append({'code': account.code,
                                                               'type': 'movement',
                                                               'name': account.name,
                                                               'amount': round(balance_account, 2)})
                        accounts[index]['amount'] = accounts[index]['amount'] + balance_account
            accounts = help_functions._update_amount(accounts)
        if type == '1':
            TOTALS.append({'total_assets': accounts[0]['amount']})
        if type == '2':
            TOTALS.append({'total_liabilities': accounts[0]['amount']})
        if type == '3':
            # TODO: Revisar está parte
            moves = []
            account_result = list(filter(lambda x: x['code'] == '3.3', accounts))
            if account_result:
                if account_result[0]['amount'] != 0.00:
                    amount = self._get_total_state_result(context)
                    internal_movement = {}
                    if amount >= 0:
                        internal_movement['code'] = '3.3.1.1'
                        internal_movement['type'] = 'movement'
                        internal_movement['name'] = 'GANANCIA NETA DEL PERÍODO'
                        internal_movement['amount'] = amount
                    else:
                        internal_movement['code'] = '3.3.2.1'
                        internal_movement['type'] = 'movement'
                        internal_movement['name'] = '(-) PÉRDIDA NETA DEL PERÍODO'
                        internal_movement['amount'] = amount
                    for account in accounts:
                        if account['code'] == '3.3':
                            account['subaccounts'].append(internal_movement)
                    TOTALS.append({'total_equity': accounts[0]['amount'] + amount})
                    return accounts
            # TODO: Si Estado de resultados es igual a 0
            amount = self._get_status_results(context)
            if amount >= 0:
                moves.append({'code': '3.3.1.1',
                              'type': 'movement',
                              'name': 'GANANCIA NETA DEL PERÍODO',
                              'amount': amount})
            else:
                moves.append({'code': '3.3.2.1',
                              'type': 'movement',
                              'name': '(-) PERDIDA NETA DEL PERÍODO',
                              'amount': amount})
            accounts.append({'code': '3.3',
                             'type': 'view',
                             'subaccounts': moves,
                             'name': 'RESULTADO DEL EJERCICIO',
                             'amount': amount,
                             'account': False,
                             'parent': False})
            accounts[0]['amount'] = accounts[0]['amount'] + amount
            TOTALS.append({'total_equity': accounts[0]['amount']})
        return accounts

    @staticmethod
    def _get_total_assets():
        """
        Total de activos
        :return:
        """
        return TOTALS[0]['total_assets']

    @staticmethod
    def _get_total_liabilities():
        """
        Total de pasivos
        :return:
        """
        return TOTALS[1]['total_liabilities']

    @staticmethod
    def _get_total_equity():
        """
        Total del patrimonio
        :return:
        """
        return TOTALS[2]['total_equity']

    @staticmethod
    def _get_total_exercise():
        """
        Total del ejercicio
        :return:
        """
        return TOTALS[1]['total_liabilities'] + TOTALS[2]['total_equity']

    @staticmethod
    def _get_accounts_order(accounts):
        """
        Cuentas ordenadas, TODO: revisar si es necesario esto
        :param accounts:
        :return:
        """
        accounts_order = sorted(accounts, key=lambda k: int(k['code'].replace('.', '')))
        return accounts_order

    @api.model
    def _get_report_values(self, docids, data=None):
        global TOTALS  # Variable de totales del reporte
        TOTALS = []
        return {
            'doc_ids': docids,
            'doc_model': 'account.financial.situation',
            'docs': self.env['account.financial.situation'].browse(docids),
            'data': data,
            'get_report': self._get_report,
            'get_total_assets': self._get_total_assets,
            'get_total_liabilities': self._get_total_liabilities,
            'get_total_exercise': self._get_total_exercise,
            'get_accounts_order': self._get_accounts_order,
        }


class FinancialSituation(models.TransientModel):
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
