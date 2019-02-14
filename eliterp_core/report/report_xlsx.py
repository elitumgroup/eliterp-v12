# -*- coding: utf-8 -*-


from odoo import models, fields, _
import logging
import base64

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    _logger.debug(_('No se puede importar librería xlsxwriter.'))


class ReportXlsxAbstract(models.AbstractModel):
    _name = 'report.report_xlsx.abstract'

    file = fields.Binary('Archivo (.xlsx)')
    file_name = fields.Char('Nombre de archivo', readonly=True)

    def create_xlsx_report(self, name, context=None):
        name = name + '.xlsx'
        workbook = xlsxwriter.Workbook(name, self.get_workbook_options())
        self.generate_xlsx_report(workbook, context)
        workbook.close()
        with open(name, "rb") as file:
            file = base64.b64encode(file.read())
        data = {
            'file': file,
            'file_name': name
        }
        return data

    def get_workbook_options(self):
        return {'in_memory': True}

    def generate_xlsx_report(self, workbook, context):
        # TODO: Revisar está función
        pass
