# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ReportVoucherParser(models.AbstractModel):
    _name = 'report.eliterp_treasury.report_voucher'

    @api.model
    def get_report_paperformat(self, docs):
        report_paperformat_id = False
        voucher_type = docs.mapped('voucher_type')
        if voucher_type and all(voucher_type):
            report_paperformat_id = self.env.ref('eliterp_core.my_paperformat_a5_landscape').id
        if not report_paperformat_id:
            report_paperformat_id = super(ReportVoucherParser, self).get_report_paperformat(docs)
        return report_paperformat_id

    @api.model
    def _get_report_values(self, docids, data=None):
        values = {
            'doc_ids': docids,
            'doc_model': 'account.voucher',
            'docs': self.env['account.voucher'].browse(docids),
            'data': data,
        }
        report_paperformat_id = self.get_report_paperformat(values['docs'])
        if report_paperformat_id:
            values.update({
                'report_paperformat_id': report_paperformat_id,
            })
        return values


class Voucher(models.Model):
    _inherit = "account.voucher"

    @api.model
    def _get_report_filename(self):
        """
        Nombre del archivo de reporte por tipo de voucher
        :return:
        """
        if self.voucher_type == 'purchase':
            return 'Pago %s' % self.name
        else:
            return 'Cobro %s' % self.name
