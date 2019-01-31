# -*- coding: utf-8 -*-

import base64
from io import StringIO
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from . import utils
from ..xades.sri import SriService

STD_FORMAT = '%d%m%Y'

class ElectronicDocument(models.AbstractModel):
    _name = 'sri.electronic.vouchers'
    _FIELDS = {
        'account.invoice': 'invoice_number',
        'account.retention': 'retention_number'
    }
    SriServiceObject = SriService()
    password = fields.Char('Clave de acceso', size=49)
    authorization_status = fields.Selection([
        ('ppr', 'En procesamiento'),
        ('aut', 'Autorizado'),
        ('nat', 'No autorizado')
    ], string='Estado de autorización', readonly=True, default='aut')
    authorization_date = fields.Datetime(
        'Fecha autorización'
    )
    type_emission = fields.Selection(
        [
            ('1', 'Normal')
        ],
        string='Tipo de emisión',
        readonly=True,
        default='1'
    )
    environment = fields.Selection(
        [
            ('1', 'Pruebas'),
            ('2', 'Producción')
        ],
        string='Entorno',
        readonly=True,
        default='2'
    )

    def _get_sequential(self):
        """
        Obtenemos el secuencial del documento
        :return:
        """
        return getattr(self, self._FIELDS[self._name])

    def _get_information_company(self, document, access_key, emission, sequential):
        """
        TODO: Información sobre la empresa
        :param document:
        :param access_key:
        :param emission:
        :param sequential:
        :return:
        """
        company = document.company_id
        point_printing = document.point_printing_id
        information_company = {
            'ambiente': self.env.user.company_id.environment,
            'tipoEmision': emission,
            'razonSocial': company.name,
            'nombreComercial': company.name,
            'ruc': company.vat,
            'claveAcceso': access_key,
            'codDoc': utils.table3['18'],
            'estab': point_printing.shop_id.establishment,
            'ptoEmi': point_printing.emission_point,
            'secuencial': sequential,
            'dirMatriz': company.street
        }
        return information_company

    @api.multi
    def _update_document(self, authorization, codes):
        """
        Actualizamos el documento
        :param auth:
        :param codes:
        :return:
        """
        date = authorization.fechaAutorizacion.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        self.write({
            'authorization': authorization.numeroAutorizacion,
            'environment': authorization.ambiente,
            'authorization_date': date,
            'authorization_status': authorization.estado,
            'password': codes[0],
            'type_emission': codes[1]
        })

    @api.one
    def add_attachment(self, xml_element):
        """
        Generamos documento a enviar a cliente
        :param xml_element:
        :param auth:
        :return:
        """
        buf = StringIO()
        buf.write(xml_element.encode('utf-8'))
        document = base64.encodestring(buf.getvalue())
        buf.close()
        attach = self.env['ir.attachment'].create(
            {
                'name': '{0}.xml'.format(self.password),
                'datas': document,
                'datas_fname': '{0}.xml'.format(self.password),
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary'
            },
        )
        return attach

    @api.multi
    def send_document(self, attachments=None, template=False):
        """
        Enviamos documento por correo electrónico al cliente
        :param attachments:
        :param t:
        :return:
        """
        self.ensure_one()
        self._logger.info('Enviando documento electrónico por correo...')
        mail_template = self.env.ref(template)
        mail_template.send_mail(
            self.id,
            email_values={'attachment_ids': attachments}
        )
        self.sent = True
        return True

    @api.multi
    def _check_date(self, date):
        """
        Validar que el envío del comprobante electrónico se realice dentro de las 24 horas posteriores a su emisión
        :param date:
        :return:
        """
        LIMIT_TO_SEND = 5
        MESSAGE_TIME_LIMIT = u' '.join([
            u'Los comprobantes electrónicos deben',
            u'enviarse con máximo 24 horas desde su emisión.']
        )
        days = (fields.Date.today() - date).days
        if days > LIMIT_TO_SEND:
            raise UserError(MESSAGE_TIME_LIMIT)

    @api.multi
    def _check_before_sent(self):
        """
        Revisar el orden de envío del comprobante electrónico por tiempo del mismo
        :return:
        """
        MESSAGE_SEQUENTIAL = ' '.join([
            u'Los documentos electrónicos deberán ser',
            u'enviados al SRI para su autorización en orden cronológico',
            'y secuencial. Por favor enviar primero el',
            ' comprobante inmediatamente anterior.'])
        FIELD = {
            'account.invoice': 'invoice_number',
            'account.retention': 'reference'
        }
        number = getattr(self, FIELD[self._name])
        sql = ' '.join([
            "SELECT a.authorization, a.%s FROM %s as a" % (FIELD[self._name], self._table),
            "WHERE state = 'open' AND %s < '%s'" % (FIELD[self._name], number),
            self._name == 'account.invoice' and "AND type = 'out_invoice'" or '',
            "ORDER BY %s DESC LIMIT 1;" % FIELD[self._name]
        ])
        self.env.cr.execute(sql)
        result = self.env.cr.fetchone()
        if not result:
            return True
        authorization, number = result
        if authorization is None and number:
            raise UserError(MESSAGE_SEQUENTIAL)
        return True

    @api.multi
    def _get_access_key(self, name='account.invoice'):
        """
        Obtenemos llave de acceso y tipo de emisiòn
        :param name:
        :return:
        """
        access_key_temporary = self._get_access_key_temporary(name)
        self.SriServiceObject._set_active_environment(self.env.user.company_id.environment)
        access_key = self.SriServiceObject.create_access_key(access_key_temporary)
        return access_key

    def _get_access_key_temporary(self, name):
        """
        Obtenemos la clave de acceso necesario según especificaciones del SRI
        :param name:
        :return:
        """
        point_printing = self.point_printing_id
        if name == 'account.invoice':
            date = self.date_invoice.strftime(STD_FORMAT)
            sequential = getattr(self, 'invoice_number')
        elif name == 'account.retention':
            date = self.date.strftime(STD_FORMAT)
            sequential = getattr(self, 'reference')
        serie = point_printing.shop_id.establishment + point_printing.emission_point
        documentation_number = self.company_id.vat
        sequence = '00000001'  # TODO: Campo de seguridad
        type_emission = self.company_id.type_emission
        # TODO: Colocar el campo documento autorizado
        access_key_temporary = (
            [date, utils.table3['18'], documentation_number],
            [serie, sequential, sequence, type_emission]
        )
        return access_key_temporary
