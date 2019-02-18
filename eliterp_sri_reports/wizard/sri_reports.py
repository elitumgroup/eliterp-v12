# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime
from itertools import groupby
import logging
import base64
from io import StringIO, BytesIO
from jinja2 import Environment, FileSystemLoader
import os
from lxml import etree
from lxml.etree import DocumentInvalid
import time
from operator import itemgetter

STD_FORMAT = '%d/%m/%Y'

ID_CUSTOMER = {
    '0': '01',
    '1': '02',
    '2': '03'
}

ID_SUPPLIER = {
    '0': '04',
    '1': '05',
    '2': '06'
}


class AccountAts(dict):
    """
    representación del archivo ATS
    >>> ats.campo = 'valor'
    >>> ats['campo']
    'valor'
    """

    def __getattr__(self, item):
        try:
            return self.__getitem__(item)
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, item, value):
        if item in self.__dict__:
            dict.__setattr__(self, item, value)
        else:
            self.__setitem__(item, value)


class Ats(models.TransientModel):
    _name = 'sri.ats'
    _description = _("Ventana para reporte ATS")
    __logger = logging.getLogger(_name)

    @api.multi
    def _render_xml(self, ats):
        """
        Generar archivo .xml de la carpeta templates
        :param ats:
        :return:
        """
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        e = Environment(loader=FileSystemLoader(template_path))
        ats_template = e.get_template('ats.xml')
        return ats_template.render(ats)

    @api.multi
    def _validate_document(self, ats):
        """
        Validar documento con plantilla .xsd
        :param ats:
        :param error_log:
        :return:
        """
        file_path = os.path.join(os.path.dirname(__file__), 'XSD/ats.xsd')
        schema_file = open(file_path, 'rb')
        xmlschema_doc = etree.parse(schema_file)
        xmlschema = etree.XMLSchema(xmlschema_doc)
        utf8_parser = etree.XMLParser(encoding='utf-8')
        root = etree.fromstring(ats.encode('utf-8'), parser=utf8_parser)
        ok = True
        if not self.no_validate:
            try:
                xmlschema.assertValid(root)
            except DocumentInvalid:
                ok = False
        return ok, xmlschema

    def _convert_date(self, date):
        """
        fecha: '2012-12-15'
        return: '15/12/2012'
        """
        return date.strftime(STD_FORMAT)

    def _get_canceled(self, period):
        """
        Obtenemos facturas de clientes canceladas y retenciones de compras (Física)
        :param period:
        :return:
        """
        domain = [
            ('state', '=', 'cancel'),
            ('period_id', '=', period.id),
            ('company_id', '=', self.company_id.id),
            ('type', '=', 'out_invoice')
        ]
        canceled = []
        for inv in self.env['account.invoice'].search(domain):
            auth = inv.sri_authorization_id
            detalleanulados = {
                'tipoComprobante': auth.code,
                'establecimiento': auth.establishment,
                'puntoEmision': auth.emission_point,
                'secuencialInicio': inv.reference[:9],
                'secuencialFin': inv.reference[:9],
                'autorizacion': auth.authorization
            }
            canceled.append(detalleanulados)
        # Retenciones anuladas
        domain_retention = [
            ('state', '=', 'cancel'),
            ('period_id', '=', period.id),
            ('company_id', '=', self.company_id.id),
            ('type', '=', 'purchase'),
            ('is_sequential', '=', True)
        ]
        for ret in self.env['account.retention'].search(domain_retention):
            authorization = ret.sri_authorization_id
            detalleanulados = {
                'tipoComprobante': authorization.code,
                'establecimiento': authorization.establishment,
                'puntoEmision': authorization.emission_point,
                'secuencialInicio': ret.withhold_number[8:17],
                'secuencialFin': ret.withhold_number[8:17],
                'autorizacion': authorization.authorization
            }
            canceled.append(detalleanulados)
        return canceled

    def _get_iva(self, retention):
        """
        Obtenemos total de valores de iva en retención
        :param retention:
        :return:
        """
        total = 0.00
        for line in retention.retention_lines:
            if line.retention_type == 'iva':
                total += line.amount
        return total

    def _get_rent(self, retention):
        """
        Obtenemos total de valores de renta en retención
        :param retention:
        :return:
        """
        total = 0.00
        for line in retention.retention_lines:
            if line.retention_type == 'rent':
                total += line.amount
        return total

    def _get_sales(self, period):
        """
        Obtenemos las ventas en el período seleccionado
        :param period:
        :return:
        """
        domain = [
            ('state', 'in', ('open', 'paid')),
            ('period_id', '=', period.id),
            ('company_id', '=', self.company_id.id),
            ('type', '=', 'out_invoice')
        ]
        sales = []
        for inv in self.env['account.invoice'].search(domain):
            detalleventas = {
                'tpIdCliente': ID_CUSTOMER[inv.partner_id.type_documentation],
                'idCliente': inv.partner_id.documentation_number,
                'parteRel': 'NO',
                'tipoComprobante': inv.sri_authorization_id.authorized_voucher_id.code,
                'tipoEm': 'F',
                'numeroComprobantes': 1,
                'baseNoGraIva': 0.00,
                'baseImponible': 0.00,
                'baseImpGrav': inv.amount_untaxed,
                'montoIva': inv.amount_tax,
                'montoIce': '0.00',
                'valorRetIva': self._get_iva(inv.retention_id) if inv.retention_id else 0.00,
                'valorRetRenta': self._get_rent(inv.retention_id) if inv.retention_id else 0.00
            }
            sales.append(detalleventas)
        sales = sorted(sales, key=itemgetter('idCliente'))
        ats_sales = []
        for ruc, group in groupby(sales, key=itemgetter('idCliente')):
            baseimp = 0.00
            nograviva = 0.00
            montoiva = 0.00
            retiva = 0.00
            impgrav = 0.00
            retrenta = 0.00
            numComp = 0
            for i in group:
                nograviva += i['baseNoGraIva']
                baseimp += i['baseImponible']
                impgrav += i['baseImpGrav']
                montoiva += i['montoIva']
                retiva += i['valorRetIva']
                retrenta += i['valorRetRenta']
                numComp += 1
            detalle = {
                'tpIdCliente': ID_CUSTOMER[inv.partner_id.type_documentation],
                'idCliente': ruc,
                'parteRel': 'NO',
                'tipoComprobante': inv.sri_authorization_id.authorized_voucher_id.code,
                'tipoEm': 'F',
                'numeroComprobantes': numComp,
                'baseNoGraIva': '%.2f' % nograviva,
                'baseImponible': '%.2f' % baseimp,
                'baseImpGrav': '%.2f' % impgrav,
                'montoIva': '%.2f' % montoiva,
                'montoIce': '0.00',
                'valorRetIva': '%.2f' % retiva,
                'valorRetRenta': '%.2f' % retrenta,
                'formaPago': '20'
            }
            ats_sales.append(detalle)
        return ats_sales

    def _get_refund(self, invoice):
        """
        TODO: Obtenemos la nota de crédito de la factura (Probar)
        :param invoice:
        :return:
        """
        return {
            'docModificado': '01',
            'estabModificado': invoice.establishment,
            'ptoEmiModificado': invoice.emission_point,
            'secModificado': invoice.reference,
            'autModificado': invoice.authorization
        }

    def _get_retention(self, retention):
        """
        Obtenemos los datos de la retención si es física (Entregada)
        :param w:
        :return:
        """
        return {
            'estabRetencion1': retention.retention_number[:3],
            'ptoEmiRetencion1': retention.retention_number[4:7],
            'secRetencion1': retention.retention_number[8:],
            'autRetencion1': retention.sri_authorization_id.authorization,
            'fechaEmiRet1': self._convert_date(retention.date_retention)
        }

    def _process_lines(self, invoice):
        """
        Obtenemos las líneas de retención de la factura
        :param invoice:
        :return:
        """
        data_air = []
        temp = {}
        withhold = invoice.retention_id
        if withhold:
            for line in withhold.retention_lines:
                if line.retention_type == 'rent':
                    if not temp.get(line.tax_id.code):
                        temp[line.tax_id.code] = {
                            'baseImpAir': 0,
                            'valRetAir': 0
                        }
                    temp[line.tax_id.code]['baseImpAir'] += line.base_taxable
                    temp[line.tax_id.code]['codRetAir'] = line.tax_id.code
                    temp[line.tax_id.code]['porcentajeAir'] = int(line.tax_id.amount)
                    temp[line.tax_id.code]['valRetAir'] += abs(line.amount)
        for k, v in temp.items():
            v.update({
                'baseImpAir': "{0:.2f}".format(v['baseImpAir']),
                'valRetAir': "{0:.2f}".format(v['valRetAir'])
            })
            data_air.append(v)
        return data_air

    def _get_retention_iva(self, invoice):
        """
        Obtenemos el monto por código de retención
        :param invoice:
        :return:
        """
        retBien10 = 0
        retServ20 = 0
        retBien = 0
        retServ = 0
        retServ100 = 0
        retention = invoice.retention_id
        if retention:
            for tax in retention.retention_lines:
                if tax.retention_type == 'iva':
                    if tax.tax_id.code == '725':
                        # Retención 30%
                        retBien += abs(tax.amount)
                    if tax.tax_id.code == '727':
                        # Retención 70%
                        retServ += abs(tax.amount)
                    if tax.tax_id.code == '729':
                        # Retención 100%
                        retServ100 += abs(tax.amount)
        return retBien10, retServ20, retBien, retServ, retServ100

    def _get_purchases(self, period, pay_limit):
        """
        Obtenemos las facturas de compras en período
        :param period:
        :param pay_limit:
        :return:
        """
        object_invoice = self.env['account.invoice']
        domain_purchase = [
            ('state', 'in', ['open', 'paid']),
            ('period_id', '=', period.id),
            ('company_id', '=', self.company_id.id),
            ('type', 'in', ['in_invoice', 'in_refund'])
        ]
        purchases = object_invoice.search(domain_purchase)
        ats_purchases = []
        for line in purchases:
            if not ID_SUPPLIER[
                       line.partner_id.type_documentation] == '06':  # TODO: Proveedores con pasaporte no se procesa
                if line.type == 'in_invoice':
                    code = '01'
                    # TODO: If line.is_sale_note: code = '02'
                else:
                    code = '04'
                detallecompras = {}
                valRetBien10, valRetServ20, valorRetBienes, valorRetServicios, valRetServ100 = self._get_retention_iva(
                    line)
                detallecompras.update({
                    'codSustento': line.proof_support_id.code,
                    'tpIdProv': ID_SUPPLIER[line.partner_id.type_documentation],
                    'idProv': line.partner_id.documentation_number,
                    'tipoComprobante': code,
                    'parteRel': 'NO',
                    'fechaRegistro': self._convert_date(line.date_invoice),
                    'establecimiento': line.serial_number[:3],
                    'puntoEmision': line.serial_number[4:],
                    'secuencial': line.invoice_number,
                    'fechaEmision': self._convert_date(line.date_invoice),
                    'autorizacion': line.authorization,
                    'baseNoGraIva': '0.00',
                    'baseImponible': '0.00',
                    'baseImpGrav': '%.2f' % line.amount_untaxed,
                    'baseImpExe': '0.00',
                    'montoIce': '0.00',
                    'montoIva': '%.2f' % line.amount_tax,
                    'valRetBien10': '0.00',
                    'valRetServ20': '0.00',
                    'valorRetBienes': '%.2f' % valorRetBienes,
                    'valRetServ50': '0.00',
                    'valorRetServicios': '%.2f' % valorRetServicios,
                    'valRetServ100': '%.2f' % valRetServ100,
                    'totbasesImpReemb': '0.00',
                    'detalleAir': self._process_lines(line)
                })
                detallecompras.update({'pay': True})
                detallecompras.update({'formaPago': line.payment_form_id.code if line.payment_form_id else '20'})
                if line.retention_id.is_sequential:
                    detallecompras.update({'retencion': True})
                    detallecompras.update(self._get_retention(line.retention_id))
                if line.type in ['out_refund', 'in_refund']:  # TODO
                    if line.invoice_reference:
                        detallecompras.update({'es_nc': True})
                        detallecompras.update(self._get_refund(line.invoice_reference))
                ats_purchases.append(detallecompras)
        return ats_purchases

    def _get_total_sales(self, period):
        """
        Obtenemos el total de ventas en dicho período
        :param period:
        :return:
        """
        sql = "SELECT type, sum(amount_untaxed) AS base \
                          FROM account_invoice \
                          WHERE type IN ('out_invoice', 'out_refund') \
                          AND state IN ('open','paid') \
                          AND period_id = '%s' and company_id = '%s'" % (period.id, self.company_id.id)
        sql += " GROUP BY type;"
        self.env.cr.execute(sql)
        res = self.env.cr.fetchall()
        result = sum(map(lambda x: x[0] == 'out_refund' and x[1] * -1 or x[1], res))
        return result

    @api.multi
    def generate_ats(self):
        ats = AccountAts()
        # Información de cabecera
        period = self.period_id
        ats.TipoIDInformante = 'R'
        ats.IdInformante = self.company_id.vat
        ats.razonSocial = self.company_id.name.replace('.', '')
        ats.Anio = period.start_date.strftime('%Y')
        ats.Mes = period.start_date.strftime('%m')
        ats.numEstabRuc = self.shop_id.establishment
        ats.totalVentas = '%.2f' % self._get_total_sales(period)
        ats.codigoOperativo = 'IVA'
        # Compras
        ats.compras = self._get_purchases(period, self.pay_limit)
        # Ventas
        ats.ventas = self._get_sales(period)
        # Ventas del establecimiento
        ats.codEstab = '001'
        ats.ventasEstab = '%.2f' % self._get_total_sales(period)
        ats.ivaComp = '0.00'
        # Anulados
        ats.anulados = self._get_canceled(period)
        # Proceso del archivo a exportar
        ats_rendered = self._render_xml(ats)
        ok, schema = self._validate_document(ats_rendered)
        buf = StringIO()
        buf.write(ats_rendered)
        out = base64.b64encode(bytes(buf.getvalue(), 'utf-8'))
        buf.close()
        buf_error = StringIO()
        for error in schema.error_log:  # Si tiene errores se imprimen en documento
            buf_error.write("ERROR ON LINE %s: %s" % (error.line, error.message.encode("utf-8")) + '\n')
        out_error = base64.b64encode(bytes(buf_error.getvalue(), 'utf-8'))
        buf_error.close()
        name = "%s-%s%s.xml" % (
            "ATS",
            period.start_date.strftime('%m'),
            period.start_date.strftime('%Y')
        )
        data2save = {
            'state': ok and 'export' or 'export_error',
            'file': out,
            'file_name': name
        }
        if not ok:
            data2save.update({
                'state': 'export_error',
                'error_file': out_error,
                'error_file_name': 'Errores.txt'
            })
        self.write(data2save)
        return {
            'name': 'ATS',
            'type': 'ir.actions.act_window',
            'res_model': 'sri.ats',
            'view_mode': ' form',
            'view_type': ' form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    @api.model
    def _default_company(self):
        """
        Obtenemos la compañía por defecto del usuario
        :return:
        """
        return self.env.user.company_id.id

    file_name = fields.Char('Nombre de archivo', size=50, readonly=True)
    error_file_name = fields.Char('Nombre del archivo de error', size=50, readonly=True)
    year_accounting = fields.Many2one(
        'account.fiscal.year',
        'Año contable',
        required=True
    )
    period_id = fields.Many2one(
        'account.period.line',
        'Período',
        required=True
    )
    company_id = fields.Many2one(
        'res.company',
        'Companía',
        default=_default_company
    )
    shop_id = fields.Many2one(
        'sale.shop',
        'No. establecimiento'
    )
    pay_limit = fields.Float('Límite de pago', default=1000)
    file = fields.Binary('Archivo XML')
    error_file = fields.Binary('Archivo de error')
    no_validate = fields.Boolean('No validar', help="Permite validar el archivo XML con esquema XSD.")
    state = fields.Selection(
        (
            ('choose', 'Elegir'),
            ('export', 'Generado'),
            ('export_error', 'Error')
        ),
        string='Estado',
        default='choose'
    )


class RetentionSummary(models.TransientModel):
    _name = 'sri.retention.summary'
    _inherit = ['report.report_xlsx.abstract', 'sri.ats']
    _description = _("Ventana para reporte de resumen de retenciones")

    def _get_lines_sales(self, context):
        """
        Obtenemos todas las líneas facturadas de ventas con sus valores de retención
        :param context:
        :return: list
        """
        data = []
        arg = []
        arg.append(('period_id', '>=', context['period_id'].id))
        arg.append(('state', 'not in', ('draft', 'cancel')))
        arg.append(('type', '=', 'out_invoice'))
        invoices = self.env['account.invoice'].search(arg)
        count = 0
        for invoice in invoices:
            count_invoice = 0
            point_printing = invoice.point_printing_id
            for line in invoice.invoice_line_ids:
                register = []
                register.append("F" if invoice.type == 'out_invoice' else "N")  # Tipo
                register.append(point_printing.shop_id.establishment)  # Establecimiento
                register.append(point_printing.emission_point)  # P. Emisión
                register.append(invoice.invoice_number)  # Secuencial
                register.append(invoice.date_invoice.strftime(STD_FORMAT))  # Fecha
                register.append(invoice.retention_number if invoice.retention_id else "-")  # No. Retención
                register.append(line.name)  # Descripción
                register.append(invoice.partner_id.name)  # Cliente
                register.append(invoice.partner_id.documentation_number)  # No. Documento
                register.append(
                    invoice.authorization if invoice.is_electronic else invoice.sri_authorization_id.authorization)  # Autorización
                register.append("-")  # S. Tributario
                register.append(0.00)  # Base iva (11)
                register.append(0.00)  # Base 0
                register.append(0.00)  # ICE
                register.append(0.00)  # Base no iva
                register.append("-")  # C. Renta
                register.append("-")  # P. Renta
                register.append(0.00)  # Monto renta
                register.append(invoice.amount_tax if count_invoice == 0 else 0.00)  # R. Base I.
                register.append("-")  # C. Iva
                register.append("-")  # P. Iva
                register.append(0.00)  # Valor iva
                register.append(0.00)  # Total de factura
                data.append(register)
                count_invoice = 1
                if len(line.invoice_line_tax_ids) == 0:
                    data[-1][14] = line.price_subtotal
                else:
                    for tax in line.invoice_line_tax_ids:
                        if tax.amount > 0:
                            data[-1][11] = line.price_subtotal
                        if tax.amount == 0:
                            data[-1][12] = line.price_subtotal
            rent = []
            iva = []
            for line in invoice.retention_id.retention_lines:
                if line.retention_type == 'rent':
                    rent.append(line)
                if line.retention_type == 'iva':
                    iva.append(line)
            count = -1
            for r in rent:
                data[count][15] = r.tax_id.code if r.tax_id.code else "-"
                data[count][16] = str(int(r.tax_id.amount)) + '%' if r.tax_id.amount else "-"
                data[count][17] = r.amount
                count = count - 1
            count = -1
            for i in iva:
                data[count][19] = i.tax_id.code if i.tax_id.code else "-"
                data[count][20] = str(int(i.tax_id.amount)) + '%' if i.tax_id.amount else "-"
                data[count][21] = i.amount
                count = count - 1
            data[-1][22] = invoice.amount_total
        return data

    def _get_lines_purchases(self, context):
        """
        Obtenemos todas las líneas facturadas de compras con sus valores de retención
        :param context:
        :return: list
        """
        data = []
        arg = []
        arg.append(('period_id', '>=', context['period_id'].id))
        arg.append(('state', 'not in', ('draft', 'cancel')))
        arg.append(('type', '=', 'in_invoice'))
        invoices = self.env['account.invoice'].search(arg)
        count = 0
        for invoice in invoices:
            count_invoice = 0
            authorization = invoice.authorization
            establishment = invoice.serial_number[:3]
            emission_point = invoice.serial_number[4:]
            for line in invoice.invoice_line_ids:
                register = []
                register.append("F" if invoice.type == 'in_invoice' else "N")  # Tipo
                register.append(establishment)  # Establecimiento
                register.append(emission_point)  # P. Emisión
                register.append(invoice.invoice_number)  # Secuencial
                register.append(invoice.date_invoice.strftime(STD_FORMAT))  # Fecha
                register.append(invoice.retention_number if invoice.retention_id else "-")  # No. Retención
                register.append(line.name)  # Descripción
                register.append(invoice.partner_id.name)  # Cliente
                register.append(invoice.partner_id.documentation_number)  # No. Documento
                register.append(authorization)  # Autorización
                register.append(invoice.proof_support_id.code)  # S. Tributario
                register.append(0.00)  # Base iva (11)
                register.append(0.00)  # Base 0
                register.append(0.00)  # ICE
                register.append(0.00)  # Base no iva
                register.append("-")  # C. Renta
                register.append("-")  # P. Renta
                register.append(0.00)  # Monto renta
                register.append(invoice.amount_tax if count_invoice == 0 else 0.00)  # R. Base I.
                register.append("-")  # C. Iva
                register.append("-")  # P. Iva
                register.append(0.00)  # Valor iva
                register.append(0.00)  # Total de factura
                data.append(register)
                count_invoice = 1
                if len(line.invoice_line_tax_ids) == 0:
                    data[-1][14] = line.price_subtotal
                else:
                    for tax in line.invoice_line_tax_ids:
                        if tax.amount > 0:
                            data[-1][11] = line.price_subtotal
                        if tax.amount == 0:
                            data[-1][12] = line.price_subtotal
            rent = []
            iva = []
            for retention_line in invoice.retention_id.retention_lines:
                if retention_line.retention_type == 'rent':
                    rent.append(retention_line)
                if retention_line.retention_type == 'iva':
                    iva.append(retention_line)
            if len(rent) == 2:
                register = []
                register.append("F" if invoice.type == 'in_invoice' else "N")  # Tipo
                register.append(establishment)  # Establecimiento
                register.append(emission_point)  # P. Emisión
                register.append(invoice.invoice_number)  # Secuencial
                register.append(invoice.date_invoice.strftime(STD_FORMAT))  # Fecha
                register.append(invoice.retention_number if invoice.retention_id else "-")  # No. Retención
                register.append(line.name)  # Descripción
                register.append(invoice.partner_id.name)  # Cliente
                register.append(invoice.partner_id.documentation_number)  # No. Documento
                register.append(authorization)  # Autorización
                register.append(invoice.proof_support_id.code)  # S. Tributario
                register.append(0.00)  # Base iva (11)
                register.append(0.00)  # Base 0
                register.append(0.00)  # ICE
                register.append(0.00)  # Base no iva
                register.append("-")  # C. Renta
                register.append("-")  # P. Renta
                register.append(0.00)  # Monto renta
                register.append(0.00)  # R. Base I.
                register.append("-")  # C. Iva
                register.append("-")  # P. Iva
                register.append(0.00)  # Valor iva
                register.append(0.00)  # Total de factura
                data.append(register)
            count = -1
            for r in rent:
                data[count][15] = r.tax_id.code if r.tax_id.code else "-"
                data[count][16] = str(int(r.tax_id.amount)) + '%' if r.tax_id.amount else "-"
                data[count][17] = r.amount if invoice.state != 'cancel' else 0.00
                count = count - 1
                if not RETENTIONS:  # No existe retenciones (código) se crea
                    RETENTIONS.append({
                        'code': r.tax_id.code,
                        'name': r.tax_id.name,
                        'subtotal': r.base_taxable if invoice.state != 'cancel' else 0.00,
                        'amount': r.amount if invoice.state != 'cancel' else 0.00,
                        'type': "rent"
                    })
                else:
                    flag = any(x['code'] == r.tax_id.code for x in RETENTIONS)
                    if flag:  # Si existe código  actualizamso monto
                        index = list(map(lambda x: x['code'], RETENTIONS)).index(r.tax_id.code)
                        RETENTIONS[index]['amount'] = RETENTIONS[index]['amount'] + (
                            r.amount if invoice.state != 'cancel' else 0.00)
                        RETENTIONS[index]['subtotal'] = RETENTIONS[index]['subtotal'] + (
                            r.base_taxable if invoice.state != 'cancel' else 0.00)
                    else:
                        RETENTIONS.append({
                            'code': r.tax_id.code,
                            'name': r.tax_id.name,
                            'subtotal': r.base_taxable if invoice.state != 'cancel' else 0.00,
                            'amount': r.amount if invoice.state != 'cancel' else 0.00,
                            'type': "rent"
                        })
            count = -1
            for i in iva:
                data[count][19] = i.tax_id.code if i.tax_id.code else "-"
                data[count][20] = str(int(i.tax_id.amount)) + '%' if i.tax_id.amount else "-"
                data[count][21] = i.amount
                count = count - 1
                if not RETENTIONS:  # No existe retenciones (código) se crea
                    RETENTIONS.append({
                        'code': i.tax_id.code,
                        'name': i.tax_id.name,
                        'subtotal': i.base_taxable if invoice.state != 'cancel' else 0.00,
                        'amount': i.amount if invoice.state != 'cancel' else 0.00,
                        'type': "iva"
                    })
                else:
                    flag = any(x['code'] == i.tax_id.code for x in RETENTIONS)
                    if flag:  # Si existe código  actualizamos monto
                        index = list(map(lambda x: x['code'], RETENTIONS)).index(i.tax_id.code)
                        RETENTIONS[index]['amount'] = RETENTIONS[index]['amount'] + (
                            i.amount if invoice.state != 'cancel' else 0.00)
                        RETENTIONS[index]['subtotal'] = RETENTIONS[index]['subtotal'] + (
                            i.base_taxable if invoice.state != 'cancel' else 0.00)
                    else:
                        RETENTIONS.append({
                            'code': i.tax_id.code,
                            'name': i.tax_id.name,
                            'subtotal': i.base_taxable if invoice.state != 'cancel' else 0.00,
                            'amount': i.amount if invoice.state != 'cancel' else 0.00,
                            'type': "iva"
                        })
            data[-1][22] = invoice.amount_total
        return data

    def generate_xlsx_report(self, workbook, context):
        global RETENTIONS  # Variable global para suma total de retenciones por código
        RETENTIONS = []
        sales = self._get_lines_sales(context)  # Lista de factura de ventas
        purchases = self._get_lines_purchases(context)  # Lista de factura de compras
        sheet = workbook.add_worksheet('103-104')
        # Formatos de celda
        bold = workbook.add_format({'bold': 1})
        title = workbook.add_format({
            'bold': True,
            'align': 'center',
            'border': 1
        })
        heading = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'align': 'center',
            'border': 1
        })
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yy'})
        sheet.write('A1', 'ANEXO DE DECLARACIÓN 103, 104', title)
        sheet.write('A3', 'COMPRAS', heading)
        columns = [
            'TIPO', 'EST.', 'P. EMI.', 'SEC.', 'FECHA', '# RET.', 'DESCRIPCIÓN', 'RAZÓN SOCIAL',
            '# DOCUMENTO', 'AUTORIZACIÓN', 'S. TRI.', 'B. IVA', 'B. CERO', 'ICE', 'B. NO IVA',
            'C. RENTA', 'P. RENTA', 'MONTO R.', 'R. BASE IVA', 'C. IVA', 'P. IVA', 'MONTO I.', 'TOTAL'
        ]
        row = 4
        col = 0
        # Variable par sumar columnas
        sum_columns = (
            ['L', 11], ['M', 12], ['N', 13], ['O', 14],
            ['R', 17], ['S', 18], ['V', 21], ['W', 22]
        )
        """
            COMRPAS
        """
        for column in columns:
            sheet.write(row, col, column, bold)
            col += 1
        row += 1
        for line in purchases:
            col = 0
            for column in line:
                if isinstance(column, str):
                    sheet.write(row, col, column)
                elif isinstance(column, datetime):
                    sheet.write(row, col, column, date_format)
                else:
                    sheet.write(row, col, column, money_format)
                col += 1
            row += 1
        sheet.write(row, 10, 'Totales', bold)
        for l, c in sum_columns:
            sum_purchases = '=SUM(%s6:%s%s)' % (l, l, str(row))  # Sumar columnas
            sheet.write(row, c, sum_purchases, money_format)
        """
            VENTAS
        """
        row += 2
        col = 0
        sheet.write('A%s' % str(row), 'VENTAS', heading)
        row += 1
        for column in columns:
            sheet.write(row, col, column, bold)
            col += 1
        row += 1
        sum_row = row + 1
        for line in sales:
            col = 0
            for column in line:
                if isinstance(column, str):
                    sheet.write(row, col, column)
                elif isinstance(column, datetime):
                    sheet.write(row, col, column, date_format)
                else:
                    sheet.write(row, col, column, money_format)
                col += 1
            row += 1
        sheet.write(row, 10, 'Totales', bold)
        for l, c in sum_columns:
            sum_sales = '=SUM(%s%s:%s%s)' % (l, str(sum_row), l, str(row))  # Sumar columnas
            sheet.write(row, c, sum_sales, money_format)
        """
             RESUMEN RENTA/IVA
        """
        row += 2
        col = 0
        sheet.write('A%s' % str(row), 'CÓDIGO DE RENTENCIÓN', heading)
        row += 1
        columns_ = [
            'CÓDIGO', 'NOMBRE', 'TOTAL'
        ]
        for column in columns_:
            sheet.write(row, col, column, bold)
            col += 1
        row += 1
        sum_row = row + 1
        data = []
        for line in RETENTIONS:
            register = []
            register.append(line['code'])
            register.append(line['name'])
            register.append(line['amount'])
            data.append(register)
        for line in data:
            col = 0
            for column in line:
                if isinstance(column, str):
                    sheet.write(row, col, column)
                else:
                    sheet.write(row, col, column, money_format)
                col += 1
            row += 1
        sum_retentions = '=SUM(C%s:C%s)' % (str(sum_row), str(row))
        sheet.write(row, 2, sum_retentions, money_format)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        :return:
        """
        context = dict(
            period_id=self.period_id
        )
        self.write(self.create_xlsx_report('Resumen de retenciones', context))
        return {
            'name': "Resumen de retenciones",
            'type': 'ir.actions.act_window',
            'res_model': 'sri.retention.summary',
            'view_mode': ' form',
            'view_type': ' form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }