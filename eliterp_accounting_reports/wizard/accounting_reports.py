# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class ReportHelpFunctions(models.AbstractModel):
    _name = 'account.report.help.functions'
    _description = _("Funciones de ayuda para reportes contables")

    def _get_account_balance(self, account, type, context):
        """
        Obtenemos el balance de cuenta
        :param account:
        :param type:
        :param doc:
        :return:
        """
        args = [
            ('account_id', '=', account.id),
            ('date', '>=', context['start_date']),
            ('date', '<=', context['end_date'])
        ]
        beginning_balance = account._get_beginning_balance(context['start_date'])
        moves = self.env['account.move.line'].search(args)
        credit = 0.00
        debit = 0.00
        for line in moves:
            credit += line.credit
            debit += line.debit
        balance = account._get_balance_nature_account(type, debit, credit)
        return round(balance + beginning_balance, 2)

    def _get_lines_type(self, context, type):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        object_account = self.env['account.account']
        accounts = []
        accounts_base = self.env['account.account'].search([
            ('code', '=ilike', type + '%'),
            ('company_id', '=', context['company_id'].id)
        ])
        for account in accounts_base:
            if not accounts:
                childs = object_account.search([('id', 'child_of', [account.id])])
                accounts.append({
                    'code': account.code,
                    'name': account.name,
                    'type': 'principal',
                    'subaccounts': [],
                    'amount':
                        list(object_account._account_balance(account, childs, context['start_date'],
                                                             context['end_date']))[2],
                    'account': False,
                    'parent': False
                })
            else:
                parent = account.parent_id
                if not parent:
                    raise UserError(_("Cuenta '%s' no tiene definida cuenta padre.") % account.name)
                childs = object_account.search([('id', 'child_of', [account.id])])
                if account.internal_type == 'view':
                    accounts.append({
                        'code': account.code,
                        'name': account.name,
                        'type': 'view',
                        'subaccounts': [],
                        'amount': list(
                            object_account._account_balance(account, childs, context['start_date'],
                                                            context['end_date']))[2],
                        'account': account,
                        'parent': parent
                    })
                else:
                    index = list(map(lambda x: x['code'], accounts)).index(parent.code)
                    accounts[index]['subaccounts'].append({
                        'code': account.code,
                        'type': 'movement',
                        'name': account.name,
                        'amount': self._get_account_balance(account, type, context)
                    })
        return accounts

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True)
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.user.company_id)


class StatusResultsPdf(models.AbstractModel):
    _name = 'report.eliterp_accounting_reports.report_status_results'
    _inherit = 'account.report.help.functions'

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

    def _get_lines(self, context, type):
        accounts = self._get_lines_type(context, type)
        if type == '4':
            TOTALS.append({'total_income': accounts[0]['amount']})
        else:
            TOTALS.append({'total_spends': accounts[0]['amount']})
        return accounts

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
    _inherit = ['report.report_xlsx.abstract', 'account.report.help.functions']
    _description = _("Ventana para estado de resultados")

    def generate_xlsx_report(self, workbook, context):
        lines_4 = self._get_lines_type(context, '4')
        lines_5 = self._get_lines_type(context, '5')
        sheet = workbook.add_worksheet('Estado de resultados')
        # Columnas
        sheet.set_column("A:A", 15)
        sheet.set_column("B:B", 50)
        sheet.set_column("C:C", 10)
        sheet.set_column("D:D", 15)
        sheet.autofilter('A3:D3')
        # Formatos
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        heading = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'align': 'center',
            'border': 1
        })
        heading_1 = workbook.add_format({
            'bold': True,
            'font_size': 11
        })
        heading_1_number = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'num_format': '#,##0.00'
        })
        heading_2 = workbook.add_format({
            'font_size': 9,
            'bold': True,
        })
        heading_2_number = workbook.add_format({
            'font_size': 9,
            'bold': True,
            'num_format': '#,##0.00'
        })
        heading_3 = workbook.add_format({
            'font_size': 8,
        })
        heading_3_number = workbook.add_format({
            'font_size': 8,
            'num_format': '#,##0.00'
        })
        # Formatos de celda
        sheet.write('A1', 'ESTADO DE RESULTADOS', title)
        columns = [
            'CÓDIGO', 'NOMBRE DE CUENTA', 'TIPO', 'BALANCE'
        ]
        row = 2
        col = 0
        for column in columns:
            sheet.write(row, col, column, heading)
            col += 1
        # 4
        row += 1
        for line in lines_4:
            if line['type'] == 'principal':
                sheet.write(row, 0, line['code'], heading_1)
                sheet.write(row, 1, line['name'], heading_1)
                sheet.write(row, 3, line['amount'], heading_1_number)
                row += 1
            else:
                sheet.write(row, 0, line['code'], heading_2)
                sheet.write(row, 1, line['name'], heading_2)
                sheet.write(row, 2, 'VISTA', heading_2)
                sheet.write(row, 3, line['amount'], heading_2_number)
                if line['subaccounts']:
                    for lsb in line['subaccounts']:
                        if float_is_zero(lsb['amount'], precision_rounding=0.01):
                            continue
                        row += 1
                        sheet.write(row, 0, lsb['code'], heading_3)
                        sheet.write(row, 1, lsb['name'], heading_3)
                        sheet.write(row, 2, 'Movimiento', heading_3)
                        sheet.write(row, 3, lsb['amount'], heading_3_number)
                row += 1
        # 5
        for line in lines_5:
            if line['type'] == 'principal':
                sheet.write(row, 0, line['code'], heading_1)
                sheet.write(row, 1, line['name'], heading_1)
                sheet.write(row, 3, line['amount'], heading_1_number)
                row += 1
            else:
                sheet.write(row, 0, line['code'], heading_2)
                sheet.write(row, 1, line['name'], heading_2)
                sheet.write(row, 2, 'VISTA', heading_2)
                sheet.write(row, 3, line['amount'], heading_2_number)
                if line['subaccounts']:
                    for lsb in line['subaccounts']:
                        if float_is_zero(lsb['amount'], precision_rounding=0.01):
                            continue
                        row += 1
                        sheet.write(row, 0, lsb['code'], heading_3)
                        sheet.write(row, 1, lsb['name'], heading_3)
                        sheet.write(row, 2, 'MOVIMIENTO', heading_3)
                        sheet.write(row, 3, lsb['amount'], heading_3_number)
                row += 1
        row += 1
        amount_4 = lines_4[0]['amount'] if lines_4 else 0.00
        amount_5 = lines_5[0]['amount'] if lines_5 else 0.00
        amount_total = amount_4 - amount_5
        heading_result_number = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'num_format': '#,##0.00',
            'bg_color': 'red'
        })
        if amount_total > 0:
            sheet.write(row, 3, amount_total, heading_1)
        else:
            sheet.write(row, 3, amount_total, heading_result_number)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        :return:
        """
        context = dict(
            company_id=self.company_id,
            start_date=self.start_date,
            end_date=self.end_date
        )
        self.write(self.create_xlsx_report('Estado de resultados', context))
        return {
            'name': "Estado de resultados",
            'type': 'ir.actions.act_window',
            'res_model': 'account.status.results',
            'view_mode': ' form',
            'view_type': ' form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting_reports.action_report_status_results').report_action(self)

    # Análisis de gastos
    company_division_id = fields.Many2one('account.company.division', string='División')
    project_id = fields.Many2one('account.project', string='Proyecto')
    account_analytic_id = fields.Many2one('account.analytic.account', 'Centro de costo')


class FinancialSituationPdf(models.AbstractModel):
    _name = 'report.eliterp_accounting_reports.report_financial_situation'
    _inherit = 'account.report.help.functions'

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

    def _get_report(self, type, context):
        accounts = self._get_lines_type(context, type)
        if type == '1':
            TOTALS.append({'total_assets': accounts[0]['amount']})
        if type == '2':
            TOTALS.append({'total_liabilities': accounts[0]['amount']})
        if type == '3':
            # Status Result, TODO: Mejorar
            accounts_4 = self._get_lines_type(context, '4')
            total_income = accounts_4[0]['amount']
            accounts_5 = self._get_lines_type(context, '5')
            total_spends = accounts_5[0]['amount']
            equity = round(total_income - total_spends, 3)
            TOTALS.append({'total_equity': accounts[0]['amount'] + equity})
        return accounts

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

    def generate_xlsx_report(self, workbook, context):
        lines_1 = self._get_lines_type(context, '1')
        lines_2 = self._get_lines_type(context, '2')
        lines_3 = self._get_lines_type(context, '3')
        sheet = workbook.add_worksheet('Estado de situación financiera')
        # Columnas
        sheet.set_column("A:A", 15)
        sheet.set_column("B:B", 50)
        sheet.set_column("C:C", 10)
        sheet.set_column("D:D", 15)
        sheet.autofilter('A3:D3')
        # Formatos
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        heading = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'align': 'center',
            'border': 1
        })
        heading_1 = workbook.add_format({
            'bold': True,
            'font_size': 11
        })
        heading_1_number = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'num_format': '#,##0.00'
        })
        heading_2 = workbook.add_format({
            'font_size': 9,
            'bold': True,
        })
        heading_2_number = workbook.add_format({
            'font_size': 9,
            'bold': True,
            'num_format': '#,##0.00'
        })
        heading_3 = workbook.add_format({
            'font_size': 8,
        })
        heading_3_number = workbook.add_format({
            'font_size': 8,
            'num_format': '#,##0.00'
        })
        # Formatos de celda
        sheet.write('A1', 'ESTADO DE SITUACIÓN FINANCIERA', title)
        columns = [
            'CÓDIGO', 'NOMBRE DE CUENTA', 'TIPO', 'BALANCE'
        ]
        row = 2
        col = 0
        for column in columns:
            sheet.write(row, col, column, heading)
            col += 1
        # 1
        row += 1
        for line in lines_1:
            if line['type'] == 'principal':
                sheet.write(row, 0, line['code'], heading_1)
                sheet.write(row, 1, line['name'], heading_1)
                sheet.write(row, 3, line['amount'], heading_1_number)
                row += 1
            else:
                sheet.write(row, 0, line['code'], heading_2)
                sheet.write(row, 1, line['name'], heading_2)
                sheet.write(row, 2, 'VISTA', heading_2)
                sheet.write(row, 3, line['amount'], heading_2_number)
                if line['subaccounts']:
                    for lsb in line['subaccounts']:
                        if float_is_zero(lsb['amount'], precision_rounding=0.01):
                            continue
                        row += 1
                        sheet.write(row, 0, lsb['code'], heading_3)
                        sheet.write(row, 1, lsb['name'], heading_3)
                        sheet.write(row, 2, 'MOVIMIENTO', heading_3)
                        sheet.write(row, 3, lsb['amount'], heading_3_number)
                row += 1
        # 2
        for line in lines_2:
            if line['type'] == 'principal':
                sheet.write(row, 0, line['code'], heading_1)
                sheet.write(row, 1, line['name'], heading_1)
                sheet.write(row, 3, line['amount'], heading_1_number)
                row += 1
            else:
                sheet.write(row, 0, line['code'], heading_2)
                sheet.write(row, 1, line['name'], heading_2)
                sheet.write(row, 2, 'VISTA', heading_2)
                sheet.write(row, 3, line['amount'], heading_2_number)
                if line['subaccounts']:
                    for lsb in line['subaccounts']:
                        if float_is_zero(lsb['amount'], precision_rounding=0.01):
                            continue
                        row += 1
                        sheet.write(row, 0, lsb['code'], heading_3)
                        sheet.write(row, 1, lsb['name'], heading_3)
                        sheet.write(row, 2, 'MOVIMIENTO', heading_3)
                        sheet.write(row, 3, lsb['amount'], heading_3_number)
                row += 1
        # 3
        for line in lines_3:
            if line['type'] == 'principal':
                sheet.write(row, 0, line['code'], heading_1)
                sheet.write(row, 1, line['name'], heading_1)
                sheet.write(row, 3, line['amount'], heading_1_number)
                row += 1
            else:
                sheet.write(row, 0, line['code'], heading_2)
                sheet.write(row, 1, line['name'], heading_2)
                sheet.write(row, 2, 'VISTA', heading_2)
                sheet.write(row, 3, line['amount'], heading_2_number)
                if line['subaccounts']:
                    for lsb in line['subaccounts']:
                        if float_is_zero(lsb['amount'], 3):
                            continue
                        row += 1
                        sheet.write(row, 0, lsb['code'], heading_3)
                        sheet.write(row, 1, lsb['name'], heading_3)
                        sheet.write(row, 2, 'MOVIMIENTO', heading_3)
                        sheet.write(row, 3, lsb['amount'], heading_3_number)
                row += 1
        row += 1

        # Status Result
        accounts_4 = self._get_lines_type(context, '4')
        total_income = accounts_4[0]['amount']
        accounts_5 = self._get_lines_type(context, '5')
        total_spends = accounts_5[0]['amount']
        equity = round(total_income - total_spends, 3)
        sheet.write(row, 1, 'PATRIMONIO + PASIVO', heading_1)
        sheet.write(row, 3, lines_2[0]['amount'] + equity, heading_1_number)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        :return:
        """
        context = dict(
            company_id=self.company_id,
            start_date=self.start_date,
            end_date=self.end_date
        )
        self.write(self.create_xlsx_report('Estado de situación financiera', context))
        return {
            'name': "Estado de situación financiera",
            'type': 'ir.actions.act_window',
            'res_model': 'account.financial.situation',
            'view_mode': ' form',
            'view_type': ' form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

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
    company_division_id = fields.Many2one('account.company.division', string='División')
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
        if not doc['account_ids']:
            base_accounts = self.env['account.account'].search([
                ('internal_type', '!=', 'view'),
                ('company_id', '=', doc['company_id'].id)
            ])  # Todas las cuentas de la compañía
        else:
            base_accounts = doc['account_ids']
        accounts = []
        data = []
        for record in base_accounts:
            accounts.append(record)
        accounts.sort(key=lambda x: x.code, reverse=False)  # Ordenamos de menor a mayor por código
        for account in accounts:
            lines = self.env['account.move.line'].search(
                [('account_id', '=', account.id), ('date', '>=', doc['start_date']), ('date', '<=', doc['end_date'])],
                order="date")  # Movimientos de la cuenta ordenamos por fecha
            beginning_balance = account._get_beginning_balance(doc['start_date'])
            balance = beginning_balance
            total_debit = 0.00
            total_credit = 0.00
            data_line = []  # Líneas de movimientos de la cuenta
            type = (account.code.split("."))[0]
            for line in lines:
                total_debit = total_debit + line.debit
                total_credit = total_credit + line.credit
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
    _inherit = ['report.report_xlsx.abstract', 'account.report.help.functions']

    _description = _("Ventana para reporte de libro mayor")

    def generate_xlsx_report(self, workbook, context):
        object = self.env['report.eliterp_accounting_reports.report_general_ledger']
        data = object._get_lines(context)
        sheet = workbook.add_worksheet('Libro mayor')
        # Columnas
        sheet.set_column("B:B", 30)
        sheet.set_column("C:C", 70)
        sheet.set_column("D:D", 20)
        sheet.set_column("E:E", 20)
        sheet.set_column("F:F", 20)
        sheet.autofilter('A3:F3')
        # Formatos
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        heading = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'align': 'center',
            'border': 1
        })
        heading_1 = workbook.add_format({
            'bold': True,
            'font_size': 11
        })
        heading_number = workbook.add_format({
            'bold': True,
            'num_format': '#,##0.00'
        })
        # Formatos de celda
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yy'})
        sheet.write('A1', 'Libro mayor contable', title)
        columns = [
            'FECHA', 'DOCUMENTO', 'DETALLE', 'DEBE', 'HABER', 'SALDO'
        ]
        row = 2
        col = 0
        for column in columns:
            sheet.write(row, col, column, heading)
            col += 1
        for line in data:
            row += 1
            sheet.write(row, 0, '{0}[{1}]'.format(line['account'], line['code']), heading_1)
            sheet.write(row, 5, line['beginning_balance'], heading_number)
            for move in line['moves']:
                row += 1
                sheet.write(row, 0, move['date'], date_format)
                sheet.write(row, 1, move['name'])
                sheet.write(row, 2, move['detail'])
                sheet.write(row, 3, move['debit'], money_format)
                sheet.write(row, 4, move['credit'], money_format)
                sheet.write(row, 5, move['balance'], money_format)
            row += 1
            sheet.write(row, 3, line['total_debit'], heading_number)
            sheet.write(row, 4, line['total_credit'], heading_number)
            sheet.write(row, 5, line['total_balance'], heading_number)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        :return:
        """
        context = dict(
            company_id=self.company_id,
            start_date=self.start_date,
            end_date=self.end_date,
            account_ids=self.account_ids
        )
        self.write(self.create_xlsx_report('Libro mayor', context))
        return {
            'name': "Libro mayor",
            'type': 'ir.actions.act_window',
            'res_model': 'account.general.ledger.report',
            'view_mode': ' form',
            'view_type': ' form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting_reports.action_report_general_ledger').report_action(self)

    account_ids = fields.Many2many('account.account', string='Cuentas contable')
