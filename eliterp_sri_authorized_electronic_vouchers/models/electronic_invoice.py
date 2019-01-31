# -*- coding: utf-8 -*-

import os
import time
import logging
import itertools
from jinja2 import Environment, FileSystemLoader
from odoo import api, models
from odoo.exceptions import UserError
from . import utils
from ..xades.sri import DocumentXML
from ..xades.xades import Xades


class Invoice(models.Model):
    _name = 'account.invoice'
    _inherit = ['account.invoice', 'sri.electronic.vouchers']
    _logger = logging.getLogger('sri.electronic.vouchers')
    TEMPLATES = {
        'out_invoice': 'out_invoice.xml'
    }

    def _get_information_invoice(self, invoice):
        """
        Devolvemos la información necesaria para el documento XML
        :param invoice:
        :return:
        """

        def fix_date(date):
            d = date.strftime('%d/%m/%Y')
            return d

        company = invoice.company_id
        partner = invoice.partner_id
        point_printing = invoice.point_printing_id
        informationInvoice = {
            'fechaEmision': fix_date(invoice.date_invoice),
            'dirEstablecimiento': point_printing.shop_id.street,
            'obligadoContabilidad': 'SI',
            'tipoIdentificacionComprador': utils.table6[partner.type_documentation],  # TODO: Calcular en formulario
            'razonSocialComprador': partner.name,
            'identificacionComprador': partner.documentation_number,
            'totalSinImpuestos': '%.2f' % (invoice.amount_untaxed),
            'totalDescuento': '0.00',
            'propina': '0.00',
            'importeTotal': '{:.2f}'.format(invoice.amount_total),
            'moneda': 'DOLAR',
            'formaPago': invoice.payment_form_id.code  # TODO: Varios códigos (Porcentajes)
        }
        # TODO
        if company.special_contributor:
            if not company.code_special_contributor:
                raise UserError('No ha determinado si es contribuyente especial.')
            informationInvoice.update({'contribuyenteEspecial': company.code_special_contributor})
        totalTaxes = []
        for tax in invoice.tax_line_ids:
            if not tax.retention_id:
                # utils.table17[tax.tax_id.tax_group_id.tax_reference]
                totalTax = {
                    'codigo': '2',
                    'codigoPorcentaje': utils.table18[tax.tax_id.tax_group_id.tax_reference],
                    'baseImponible': '{:.2f}'.format(tax.base),
                    'valor': '{:.2f}'.format(tax.amount)
                }
                totalTaxes.append(totalTax)
        informationInvoice.update({'totalConImpuestos': totalTaxes})
        return informationInvoice

    def _details(self, invoice):
        """
        Detalle de la factura (Líneas)
        :param invoice:
        :return:
        """

        def fix_chars(code):
            special = [
                [u'%', ' '],
                [u'º', ' '],
                [u'Ñ', 'N'],
                [u'ñ', 'n']
            ]
            for f, r in special:
                code = code.replace(f, r)
            return code

        details = []
        for line in invoice.invoice_line_ids:
            productCode = line.product_id and \
                          line.product_id.default_code and \
                          fix_chars(line.product_id.default_code) or '001'
            price = line.price_unit * (1 - (line.discount or 0.00) / 100.0)
            discount = (line.price_unit - price) * line.quantity
            detail = {
                'codigoPrincipal': productCode,
                'descripcion': fix_chars(line.name.strip()),
                'cantidad': '%.6f' % (line.quantity),
                'precioUnitario': '%.6f' % (line.price_unit),
                'descuento': '%.2f' % discount,
                'precioTotalSinImpuesto': '%.2f' % (line.price_subtotal)
            }
            taxes = []
            for tax_line in line.invoice_line_tax_ids:
                tax = {
                    'codigo': '2',
                    'codigoPorcentaje': utils.table18[tax_line.tax_group_id.tax_reference],
                    'tarifa': tax_line.amount,
                    'baseImponible': '{:.2f}'.format(line.price_subtotal),
                    'valor': '{:.2f}'.format(line.price_subtotal *
                                             tax_line.amount)
                }
                taxes.append(tax)
            detail.update({'impuestos': taxes})
            details.append(detail)
        return {'detalles': details}

    def _compute_discount(self, details):
        """
        Calculamos el total de descuentos
        :param details:
        :return:
        """
        total = sum([float(detail['descuento']) for detail in details['detalles']])
        return {'totalDescuento': total}

    def render_document(self, invoice, access_key, emission):
        """
        Devolvemos el XML del documento actual con todos sus datos
        :param invoice:
        :param access_key:
        :param emission:
        :return:
        """
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        environment = Environment(loader=FileSystemLoader(template_path))
        invoice_template = environment.get_template(self.TEMPLATES[self.type])
        data = {}
        data.update(self._get_information_company(invoice, access_key, emission, invoice.invoice_number))
        data.update(self._get_information_invoice(invoice))
        details = self._details(invoice)
        data.update(details)
        data.update(self._compute_discount(details))
        electronic_invoice = invoice_template.render(data)
        return electronic_invoice

    def render_authorized_electronic_invoice(self, authorization):
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        environment = Environment(loader=FileSystemLoader(template_path))
        electronic_invoice_template = environment.get_template('authorized_electronic_invoice.xml')
        authorization_xml = {
            'estado': authorization.estado,
            'numeroAutorizacion': authorization.numeroAutorizacion,
            'ambiente': authorization.ambiente,
            'fechaAutorizacion': str(authorization.fechaAutorizacion.strftime("%d/%m/%Y %H:%M:%S")),
            'comprobante': authorization.comprobante
        }
        authorized_invoice = electronic_invoice_template.render(authorization_xml)
        return authorized_invoice

    @api.multi
    def action_electronic_voucher(self):
        """
        Método de generación de factura electrónica, CELERY
        :return:
        """
        for record in self:
            if record.type not in ['out_invoice', 'out_refund']:
                continue
            self._check_date(record.date_invoice)
            self._check_before_sent()
            access_key = self._get_access_key(name='account.invoice')
            electronic_invoice = self.render_document(record, access_key, '1')  # Off-line
            invoice_xml = DocumentXML(electronic_invoice, record.type)
            invoice_xml.validate_xml()
            xml_file = os.path.join('/home/odoo/Documents/generated',
                                    'in_invoice-generated-' + record.invoice_number + ".xml")
            file = open(xml_file, "w")
            file.write(electronic_invoice)
            file.close()
            xades = Xades()
            file_pk12 = record.company_id.electronic_signature
            password = record.company_id.password_electronic_signature
            signed_document = xades.sign(record.invoice_number, file_pk12, password)
            ok, errors = invoice_xml.send_receipt(signed_document)
            if not ok:
                raise UserError(errors)
            authorization, m = invoice_xml.request_authorization(access_key)
            if not authorization:
                msg = ' '.join(list(itertools.chain(*m)))
                raise UserError(msg)
            electronic_authorization = self.render_authorized_electronic_invoice(authorization)
            self.update_document(authorization, [access_key, '1'])
            attach = self.add_attachment(electronic_authorization, authorization)
            message = """
            DOCUMENTO ELECTRÓNICO GENERADO <br><br>
            CLAVE DE ACCESO: %s <br>
            NÚMERO DE AUTORIZACIÓN %s <br>
            FECHA AUTORIZACIÓN: %s <br>
            ESTADO DE AUTORIZACIÓN: %s <br>
            AMBIENTE: %s <br>
            """ % (
                self.password,
                self.authorization_electronic,
                self.authorization_date,
                self.authorization_status,
                self.environment
            )
            # Configurar correo electrónico de salida en sistema
            # Enviar factura por correo electrónico
            self.message_post(body=message)
            self.send_document(
                attachments=[a.id for a in attach],
                template='eliterp_sri_authorized_electronic_vouchers.mail_template_electronic_invoice')
