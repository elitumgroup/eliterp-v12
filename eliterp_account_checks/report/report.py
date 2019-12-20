# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from datetime import datetime
from odoo import api, fields, models


class ChecksReceivedReportPDF(models.AbstractModel):
    _name = 'report.eliterp_account_checks.eliterp_report_checksr'

    def get_facturas(self, facturas):
        bill_number = ""
        count = 0
        for f in facturas:
            if count == 0:
                bill_number = bill_number + f.name[-5:]
                count = count + 1
            else:
                bill_number = bill_number + "-" + f.name[-5:]
        return bill_number

    def _get_lines(self, doc):
        data = []
        arg = []
        if doc['customer_type'] != 'todos':
            arg.append(('partner_id', '=', doc['partner'].id))
        arg.append(('voucher_type', '=', 'sale'))
        vouchers = self.env['account.voucher'].search(arg)
        for voucher in vouchers:
            facturas = self.get_facturas(voucher.out_invoice_line)
            for line in voucher.collection_line:
                if line.type_payment == 'check':
                    if line.check_type == 'current':
                        datev = voucher.date
                    else:
                        datev = line.create_date
                    if doc['start_date'] <= datev <= doc['end_date']:
                        data.append({
                            'date_received': voucher.date,
                            'document_date': voucher.date if line.check_type == 'corriente' else line.create_date,
                            'credit_date': voucher.date if line.check_type == 'corriente' else line.date_due,
                            'partner': voucher.partner_id.name,
                            'facturas': facturas,
                            'issuing_bank': line.bank_id.name,
                            'number_check': line.check_number,
                            'amount': line.amount,
                        })
        return data

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.checks.received.report',
            'docs': self.env['eliterp.checks.received.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class ChecksReceivedReport(models.TransientModel):
    _name = 'eliterp.checks.received.report'

    _description = "Ventana para reporte de cheques recibidos"

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_account_checks.eliterp_action_report_checks_received_report').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    customer_type = fields.Selection([('todos', 'Todos'), ('partner', 'Individual')], 'Tipo de Cliente',
                                     default='todos')
    partner = fields.Many2one('res.partner', 'Cliente')
    bank_type = fields.Selection([('todos', 'Todos'), ('bank', 'Individual')], 'Tipo de Asesor', default='todos')
    bank = fields.Many2one('res.bank', 'Banco')


class ChecksIssuedReportPDF(models.AbstractModel):
    _name = 'report.eliterp_account_checks.eliterp_report_checksi'

    def _get_state(self, state):
        """
        Obtenemos el estado del cheque
        :param voucher:
        :return:
        """
        if state == 'issued':
            return 'EMITIDO'
        elif state == 'protested':
            return 'ANULADO'
        elif state == 'delivered':
            return 'ENTREGADO'
        else:
            return 'COBRADO'

    def _get_lines(self, doc):
        """
        Obtenemos las líneas de reporte
        :param doc:
        :return:
        """
        data = []
        arg = []
        if doc['filter_date'] == 'one':
            arg.append(('date', '>=', doc['start_date']))
            arg.append(('date', '<=', doc['end_date']))
        else:
            arg.append(('check_date', '>=', doc['start_date']))
            arg.append(('check_date', '<=', doc['end_date']))
        arg.append(('type', '=', 'issued'))
        arg.append(('bank_journal_id', 'in', doc['bank_ids']._ids))
        checks = self.env['account.checks'].search(arg)
        for check in checks:
            data.append({
                'bank_id': check.bank_id.name,
                'date': check.date,
                'check_date': check.check_date,
                'type': 'COEG',
                'check_number': check.name,
                'concept': check.voucher_id.reference,
                'beneficiary': check.recipient,
                'amount': check.amount,
                'state': self._get_state(check.state)
            })

        return data

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.checks.issued.report',
            'docs': self.env['eliterp.checks.issued.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class ChecksIssuedReport(models.TransientModel):
    _name = 'eliterp.checks.issued.report'

    _description = "Ventana para reporte de cheques emitidos"

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        """
        self.ensure_one()
        return self.env.ref('eliterp_account_checks.eliterp_action_report_checks_issued_xlsx').report_action(self)

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_account_checks.eliterp_action_report_checks_issued_report').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    filter_date = fields.Selection([('one', 'Emisión'), ('two', 'Fecha de cheque')], 'Filtrar por', default='one')
    bank_ids = fields.Many2many('account.journal', string='Bancos', required=True)
