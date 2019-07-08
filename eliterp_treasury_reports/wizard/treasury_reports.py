# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
import datetime


class AccountsReceivableReport(models.TransientModel):
    _name = 'accounts.treasury.report'

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    state = fields.Selection([('all', 'Todas'), ('due', 'Vencidas')], default='all', string='Estado')
    delinquency = fields.Integer('Morosidad', default=0,
                                 help="Técnico: Filtrar solo con días de morosidad especificado.")
    partner_ids = fields.Many2many('res.partner', string='Empresas')


class AccountsReceivableReportPDF(models.AbstractModel):
    _name = 'report.eliterp_treasury_reports.report_accounts_receivable'

    def _get_lines(self, doc):
        data = []
        arg = []
        if doc['partner_ids']:
            arg.append(('partner_id', 'in', doc['partner_ids'].ids))
        if doc['state'] != 'all':
            arg.append(('date_due', '<=', fields.date.today()))
        arg.append(('date_invoice', '>=', doc['start_date']))
        arg.append(('date_invoice', '<=', doc['end_date']))
        arg.append(('state', '=', 'open'))
        arg.append(('type', '=', 'out_invoice'))
        arg.append(('company_id', '=', self.env.user.company_id.id))
        invoices = self.env['account.invoice'].search(arg)
        count = 0
        for invoice in invoices:
            count += 1
            expiration_date = invoice.date_due
            delinquency = doc['delinquency']
            days_expire = 0
            defeated = False
            overcome = False
            if invoice.residual != 0.00:
                if fields.date.today() > expiration_date:
                    delinquency = (fields.date.today() - expiration_date).days
                    defeated = True
            if invoice.residual != 0.00:
                if expiration_date < fields.date.today():
                    overcome = True
                    days_expire = (expiration_date - fields.date.today()).days
            amount = invoice.amount_total_signed
            data.append({
                'partner': invoice.partner_id.name,
                'number': invoice.reference,
                'amount': amount,
                'outstanding_balance': invoice.residual,
                'expedition_date': invoice.date_invoice,
                'expiration_date': invoice.date_due,
                'delinquency': delinquency,
            })
            # TODO
            if True:
                data[-1].update(
                    {'overcome_30': amount if overcome == True and (days_expire >= 1 and days_expire <= 30) else float(
                        0.00),
                     'overcome_90': amount if overcome == True and (days_expire >= 31 and days_expire <= 90) else 0.00,
                     'overcome_180': amount if overcome == True and (
                             days_expire >= 91 and days_expire <= 180) else 0.00,
                     'overcome_360': amount if overcome == True and (
                             days_expire >= 181 and days_expire <= 360) else 0.00,
                     'overcome_mayor': amount if overcome == True and (days_expire > 360) else 0.00,
                     'defeated_30': amount if defeated == True and (delinquency >= 1 and delinquency <= 30) else 0.00,
                     'defeated_90': amount if defeated == True and (delinquency >= 31 and delinquency <= 90) else 0.00,
                     'defeated_180': amount if defeated == True and (
                             delinquency >= 91 and delinquency <= 180) else 0.00,
                     'defeated_360': amount if defeated == True and (
                             delinquency >= 181 and delinquency <= 360) else 0.00,
                     'defeated_mayor': amount if defeated == True and (delinquency > 360) else 0.00, })
        return data

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'accounts.receivable.report',
            'docs': self.env['accounts.receivable.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class AccountsReceivableReport(models.TransientModel):
    _name = 'accounts.receivable.report'
    _inherit = 'accounts.treasury.report'
    _description = _("Ventana para reporte de cuentas por cobrar")

    @api.multi
    def print_report_pdf(self):
        self.ensure_one()
        return self.env.ref('eliterp_treasury_reports.action_report_accounts_receivable').report_action(self)

    @api.multi
    def print_report_xlsx(self):
        self.ensure_one()
        return self.env.ref('eliterp_treasury_reports.action_report_accounts_receivable_xlsx').report_action(self)


class AccountsReceivableReportExcel(models.AbstractModel):
    _name = 'report.eliterp_treasury_reports.report_accounts_receivable_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_treasury_reports.report_accounts_receivable']._get_lines(context)
        sheet = workbook.add_worksheet('Cuentas por cobrar')
        # Formatos
        center_format = workbook.add_format({'align': 'center'})
        _right_format = workbook.add_format({'align': 'right', 'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yy'})
        title = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center'
        })
        # Columnas
        sheet.set_column("A:A", 37)
        sheet.set_column("B:B", 17.29)
        sheet.set_column("C:C", 9)
        sheet.set_column("D:D", 16.5)
        sheet.set_column("E:E", 14.25)
        sheet.set_column("F:F", 14.24)
        sheet.set_column("G:G", 11.6)
        sheet.set_column("H:H", 8.6)
        sheet.set_column("I:I", 8.6)
        sheet.set_column("J:J", 8.6)
        sheet.set_column("K:K", 8.6)
        sheet.set_column("K:K", 8.6)
        sheet.set_column("L:L", 8.6)
        sheet.set_column("M:M", 8.6)
        sheet.set_column("N:N", 8.6)
        sheet.set_column("O:O", 8.6)
        sheet.set_column("P:P", 8.6)
        sheet.set_column("Q:Q", 8.6)

        # Filas
        sheet.set_default_row(15)
        # Datos
        sheet.merge_range('A1:Q2', 'Cuentas por cobrar', title)
        sheet.merge_range(2, 7, 2, 11, "VALORES POR VENCER", center_format)
        sheet.merge_range(2, 12, 2, 16, "VALORES VENCIDOS", center_format)
        sheet.merge_range(3, 7, 3, 11, "ANTIGÜEDAD DE CARTERA (DÍAS)", center_format)
        sheet.merge_range(3, 12, 3, 16, "ANTIGÜEDAD DE CARTERA (DÍAS)", center_format)
        sheet.write(4, 0, "CLIENTE")
        sheet.write(4, 1, "NO. FACTURA")
        sheet.write(4, 2, "VALOR")
        sheet.write(4, 3, "SALDO PENDIENTE")
        sheet.write(4, 4, "FECHA EMISION")
        sheet.write(4, 5, "FECHA VENCIMIENTO")
        sheet.write(4, 6, "MOROSIDAD")
        sheet.write(4, 7, "1-30")
        sheet.write(4, 8, "31-90")
        sheet.write(4, 9, "91-180")
        sheet.write(4, 10, "181-360")
        sheet.write(4, 11, "MAYOR A")
        sheet.write(4, 12, "1-30")
        sheet.write(4, 13, "31-90")
        sheet.write(4, 14, "91-180")
        sheet.write(4, 15, "181-360")
        sheet.write(4, 16, "MAYOR A")
        row = 5
        for r in data:
            sheet.write(row, 0, r['partner'])
            sheet.write(row, 1, r['number'])
            sheet.write(row, 2, r['amount'], _right_format)
            sheet.write(row, 3, r['outstanding_balance'], _right_format)
            sheet.write(row, 4, r['expedition_date'], date_format)
            sheet.write(row, 5, r['expiration_date'], date_format)
            sheet.write(row, 6, r['delinquency'], _right_format)
            sheet.write(row, 7, r['overcome_30'], _right_format)
            sheet.write(row, 8, r['overcome_90'], _right_format)
            sheet.write(row, 9, r['overcome_180'], _right_format)
            sheet.write(row, 10, r['overcome_360'], _right_format)
            sheet.write(row, 11, r['overcome_mayor'], _right_format)
            sheet.write(row, 12, r['defeated_30'], _right_format)
            sheet.write(row, 13, r['defeated_90'], _right_format)
            sheet.write(row, 14, r['defeated_180'], _right_format)
            sheet.write(row, 15, r['defeated_360'], _right_format)
            sheet.write(row, 16, r['defeated_mayor'], _right_format)
            row += 1


class AccountsPayableReportPDF(models.AbstractModel):
    _name = 'report.eliterp_treasury_reports.report_accounts_payable'

    def _get_payments(self, invoice, start, end):
        payments = invoice._get_payments_vals()
        if not payments:
            return 0.00
        amount = 0.00
        for payment in filter(lambda x: start <= x['date'] <= end, payments):
            amount += payment['amount']
        return amount

    def _get_lines(self, doc):
        data = []
        arg = []
        if doc['partner_ids']:
            arg.append(('partner_id', 'in', doc['partner_ids'].ids))
        if doc['state'] != 'all':
            arg.append(('date_due', '<=', fields.date.today()))
        arg.append(('date_invoice', '>=', doc['start_date']))
        arg.append(('date_invoice', '<=', doc['end_date']))
        arg.append(('state', 'in', ('open', 'paid')))
        arg.append(('type', '=', 'in_invoice'))
        arg.append(('company_id', '=', self.env.user.company_id.id))
        invoices = self.env['account.invoice'].search(arg)
        count = 0
        for invoice in invoices:
            if invoice.residual == 0.00:
                continue
            count += 1
            expiration_date = invoice.date_due
            refunds = self.env['account.invoice'].search([('refund_invoice_id', '=', invoice.id)])
            delinquency = doc['delinquency']
            days_expire = 0
            defeated = False
            overcome = False
            if invoice.residual != 0.00:
                if fields.date.today() > expiration_date:
                    delinquency = (fields.date.today() - expiration_date).days
                    defeated = True
            if invoice.residual != 0.00:
                if expiration_date < fields.date.today():
                    overcome = True
                    days_expire = (expiration_date - fields.date.today()).days
            amount = invoice.amount_total
            amount_pays = self._get_payments(invoice, doc['start_date'], doc['end_date'])
            residual =  amount - amount_pays
            if expiration_date > fields.date.today():
                delinquency = fields.date.today() - expiration_date
            data.append({
                'provider': invoice.partner_id.name,
                'number': invoice.reference,
                'subtotal': invoice.amount_untaxed,
                'iva': invoice.amount_tax,
                'amount': amount,
                'amount_credit_note': sum(line.amount_untaxed for line in refunds) if refunds else 0.00,
                'amount_retention': invoice.amount_retention if invoice.retention_id else 0.00,
                'pays': amount_pays,
                'outstanding_balance': residual,
                'broadcast_date': invoice.date_invoice,
                'expiration_date': invoice.date_due,
                'delinquency': delinquency,
            })
            if True:
                data[-1].update(
                    {
                        'overcome_30': residual if overcome and (days_expire >= 1 and days_expire <= 30) else float(
                            0.00),
                        'overcome_90': residual if overcome and (days_expire >= 31 and days_expire <= 90) else 0.00,
                        'overcome_180': residual if overcome and (days_expire >= 91 and days_expire <= 180) else 0.00,
                        'overcome_360': residual if overcome and (days_expire >= 181 and days_expire <= 360) else 0.00,
                        'overcome_mayor': residual if overcome and (days_expire > 360) else 0.00,
                        'defeated_30': residual if defeated and (delinquency >= 1 and delinquency <= 30) else 0.00,
                        'defeated_90': residual if defeated and (delinquency >= 31 and delinquency <= 90) else 0.00,
                        'defeated_180': residual if defeated and (delinquency >= 91 and delinquency <= 180) else 0.00,
                        'defeated_360': residual if defeated and (delinquency >= 181 and delinquency <= 360) else 0.00,
                        'defeated_mayor': residual if defeated and (delinquency > 360) else 0.00,
                    })
        return data

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'accounts.payable.report',
            'docs': self.env['accounts.payable.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class AccountsPayableReport(models.TransientModel):
    _name = 'accounts.payable.report'
    _inherit = 'accounts.treasury.report'
    _description = _("Ventana para reporte de cuentas por pagar")

    @api.multi
    def print_report_pdf(self):
        self.ensure_one()
        return self.env.ref('eliterp_treasury_reports.action_report_accounts_payable').report_action(self)

    @api.multi
    def print_report_xlsx(self):
        self.ensure_one()
        return self.env.ref('eliterp_treasury_reports.action_report_accounts_payable_xlsx').report_action(self)


class AccountsPayableReportExcel(models.AbstractModel):
    _name = 'report.eliterp_treasury_reports.report_accounts_payable_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_treasury_reports.report_accounts_payable']._get_lines(context)
        sheet = workbook.add_worksheet('CUENTAS POR PAGAR')
        # Formatos
        center_format = workbook.add_format({'align': 'center'})
        _right_format = workbook.add_format({'align': 'right', 'num_format': '#,##0.00'})
        _right_format_p = workbook.add_format({
            'align': 'right',
            'num_format': '#,##0.00',
            'color': 'red'
        })
        _right_format_r = workbook.add_format({
            'align': 'right',
            'num_format': '#,##0.00',
            'bold': True,
            'font_size': 12,
            'bg_color': '#D3D3D3'
        })
        date_format = workbook.add_format({'num_format': 'dd/mm/yy'})
        title = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center'
        })
        # Columnas
        sheet.set_column("A:A", 50)
        sheet.set_column("B:B", 20)
        sheet.set_column("C:C", 10)
        sheet.set_column("D:D", 7.5)
        sheet.set_column("E:E", 12.5)
        sheet.set_column("F:F", 10)
        sheet.set_column("G:G", 10)
        sheet.set_column("H:H", 15)
        sheet.set_column("I:I", 20)
        sheet.set_column("J:J", 15)
        sheet.set_column("K:K", 15)
        sheet.set_column("L:L", 15)
        sheet.set_column("M:M", 8.6)
        sheet.set_column("N:N", 8.6)
        sheet.set_column("O:O", 8.6)
        sheet.set_column("P:P", 8.6)
        sheet.set_column("Q:Q", 8.6)
        sheet.set_column("R:R", 8.6)
        sheet.set_column("S:S", 8.6)
        sheet.set_column("T:T", 8.6)
        sheet.set_column("U:U", 8.6)
        sheet.set_column("V:V", 8.6)

        # Filas
        sheet.set_default_row(15)
        # Datos
        sheet.merge_range('A1:V2', 'Cuentas por pagar', title)
        sheet.merge_range(2, 12, 2, 16, "VALORES POR VENCER", center_format)
        sheet.merge_range(2, 17, 2, 21, "VALORES VENCIDOS", center_format)
        sheet.merge_range(3, 12, 3, 16, "ANTIGÜEDAD DE CARTERA (DÍAS)", center_format)
        sheet.merge_range(3, 17, 3, 21, "ANTIGÜEDAD DE CARTERA (DÍAS)", center_format)
        sheet.write(4, 0, "PROVEEDOR")
        sheet.write(4, 1, "NO. FACTURA")
        sheet.write(4, 2, "SUBTOTAL")
        sheet.write(4, 3, "IVA")
        sheet.write(4, 4, "TOTAL")
        sheet.write(4, 5, "N.C")
        sheet.write(4, 6, "RETENIDO")
        sheet.write(4, 7, "PAGOS")
        sheet.write(4, 8, "SALDO PENDIENTE")
        sheet.write(4, 9, "FECHA EMISIÓN")
        sheet.write(4, 10, "VENCIMIENTO")
        sheet.write(4, 11, "MOROSIDAD")
        sheet.write(4, 12, "1-30")
        sheet.write(4, 13, "31-90")
        sheet.write(4, 14, "91-180")
        sheet.write(4, 15, "181-360")
        sheet.write(4, 16, "MAYOR A")
        sheet.write(4, 17, "1-30")
        sheet.write(4, 18, "31-90")
        sheet.write(4, 19, "91-180")
        sheet.write(4, 20, "181-360")
        sheet.write(4, 21, "MAYOR A")
        row = 5
        for r in data:
            sheet.write(row, 0, r['provider'])
            sheet.write(row, 1, r['number'])
            sheet.write(row, 2, r['subtotal'], _right_format)
            sheet.write(row, 3, r['iva'], _right_format)
            sheet.write(row, 4, r['amount'], _right_format)

            # Pagado
            sheet.write(row, 5, r['amount_credit_note'], _right_format_p)
            sheet.write(row, 6, r['amount_retention'], _right_format_p)
            sheet.write(row, 7, r['pays'], _right_format_p)

            sheet.write(row, 8, r['outstanding_balance'], _right_format_r)

            sheet.write(row, 9, r['broadcast_date'], date_format)
            sheet.write(row, 10, r['expiration_date'], date_format)
            sheet.write(row, 11, r['delinquency'], _right_format)
            sheet.write(row, 12, r['overcome_30'], _right_format)
            sheet.write(row, 13, r['overcome_90'], _right_format)
            sheet.write(row, 14, r['overcome_180'], _right_format)
            sheet.write(row, 15, r['overcome_360'], _right_format)
            sheet.write(row, 16, r['overcome_mayor'], _right_format)
            sheet.write(row, 17, r['defeated_30'], _right_format)
            sheet.write(row, 18, r['defeated_90'], _right_format)
            sheet.write(row, 19, r['defeated_180'], _right_format)
            sheet.write(row, 20, r['defeated_360'], _right_format)
            sheet.write(row, 21, r['defeated_mayor'], _right_format)
            row += 1
