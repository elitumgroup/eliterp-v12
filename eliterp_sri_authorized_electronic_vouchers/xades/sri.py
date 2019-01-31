# -*- coding: utf-8 -*-

import os
import base64
import logging
from odoo.exceptions import ValidationError

from lxml import etree
from lxml.etree import fromstring, DocumentInvalid

try:
    from suds.client import Client
except ImportError:
    logging.getLogger('xades.sri').info('Instalar librería suds-jurko')

from ..models import utils
from .xades import CheckDigit

SCHEMAS = {
    'out_invoice': 'schemas/out_invoice.xsd'
}


class DocumentXML(object):
    _schema = False
    document = False

    @classmethod
    def __init__(self, document, type='out_invoice'):
        """
        document: XML representation
        type: determinate schema
        """
        parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
        self.document = fromstring(document.encode('utf-8'), parser=parser)
        self.type_document = type
        self._schema = SCHEMAS[self.type_document]
        self.signed_document = False
        self.logger = logging.getLogger('xades.sri')

    @classmethod
    def validate_xml(self):
        """
        Validar esquema XML
        :return:
        """
        self.logger.info('Validación de esquema.')
        self.logger.debug(etree.tostring(self.document, pretty_print=True))
        file_path = os.path.join(os.path.dirname(__file__), self._schema)
        schema_file = open(file_path)
        xmlschema_doc = etree.parse(schema_file)
        xmlschema = etree.XMLSchema(xmlschema_doc)
        try:
            xmlschema.assertValid(self.document)
        except DocumentInvalid as e:
            raise ValidationError("Error con mensaje:\n\n" + str(e))

    @classmethod
    def send_receipt(self, xml_string):
        """
        Método que envía el XML al WS del SRI
        :param xml_string:
        :return:
        """
        base_64 = base64.b64encode(xml_string.encode("UTF-8"))
        data = base_64.decode("UTF-8")
        # Modo offline
        self.logger.info('Enviando documento para recepción en el SRI, Cliente...')
        if not utils.check_service('test'):
            raise ('Error SRI', 'Servicio SRI no disponible y/o sistema sin conexión a Internet.')
        client = Client(SriService.get_active_ws()[0])
        result = client.service.validarComprobante(data)
        errors = []
        type = ''
        for c in result.comprobantes:
            for m in c[1][0].mensajes:
                type = m[1][0].tipo
                result = [type, m[1][0].mensaje]
                result.append(getattr(m[1][0], 'informacionAdicional', ''))
                errors.append(' '.join(result))
        if type == 'ERROR':
            return False, ', '.join(errors)
        else:
            return True, errors

    def request_authorization(self, access_key):
        """
        Obtenemos la respuesta del servicio web del SRI
        :param access_key:
        :return:
        """
        messages = []
        client = Client(SriService.get_active_ws()[1])
        result = client.service.autorizacionComprobante(access_key)
        self.logger.debug("Respuesta de autorizacionComprobante:SRI")
        self.logger.debug(result)
        autorizacion = result.autorizaciones[0][0]
        mensajes = autorizacion.mensajes and autorizacion.mensajes[0] or []
        self.logger.info('Estado de autorización %s' % autorizacion.estado)
        for m in mensajes:
            self.logger.error('{0} {1} {2}'.format(
                m.identificador, m.mensaje, m.tipo, m.informacionAdicional)
            )
            messages.append([m.identificador, m.mensaje,
                             m.tipo, m.informacionAdicional])
        if not autorizacion.estado == 'AUTORIZADO':
            return False, messages
        return autorizacion, messages


class SriService(object):
    __ENVIRONMENT_TEST = '1'
    __ENVIRONMENT_PRODUCTION = '2'
    __ACTIVE_ENV = False

    __WS_TEST_RECEIVE = 'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes?wsdl'
    __WS_TEST_AUTH = 'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantes?wsdl'
    __WS_RECEIV = 'https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes?wsdl'
    __WS_AUTH = 'https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantes?wsdl'

    __WS_TESTING = (__WS_TEST_RECEIVE, __WS_TEST_AUTH)
    __WS_PRODUCTION = (__WS_RECEIV, __WS_AUTH)

    _WSDL = {
        __ENVIRONMENT_TEST: __WS_TESTING,
        __ENVIRONMENT_PRODUCTION: __WS_PRODUCTION
    }
    __WS_ACTIVE = __WS_TESTING

    @classmethod
    def _set_active_environment(self, environment):
        """
        Seteamos el ambiente de trabajo de la compañía
        :param environment:
        :return:
        """
        if environment == self.__ENVIRONMENT_TEST:
            self.__ACTIVE_ENV = self.__ENVIRONMENT_TEST
        else:
            self.__ACTIVE_ENV = self.__ENVIRONMENT_PRODUCTION
        self.__WS_ACTIVE = self._WSDL[self.__ACTIVE_ENV]

    @classmethod
    def get_active_environment(self):
        return self.__ACTIVE_ENV

    @classmethod
    def get_env_test(self):
        return self.__ENVIRONMENT_TEST

    @classmethod
    def get_env_production(self):
        return self.__ENVIRONMENT_PRODUCTION

    @classmethod
    def get_ws_test(self):
        return self.__WS_TEST_RECEIVE, self.__WS_TEST_AUTH

    @classmethod
    def get_ws_production(self):
        return self.__WS_RECEIV, self.__WS_AUTH

    @classmethod
    def get_active_ws(self):
        return self.__WS_ACTIVE

    @classmethod
    def create_access_key(self, values):
        """
        Creamos la clave de acceso
        :param values:
        :return:
        """
        environment = self.get_active_environment()
        data = ''.join(values[0] + [environment] + values[1])
        module11 = CheckDigit.compute_mod11(data)
        access_key = ''.join([data, str(module11)])
        return access_key
