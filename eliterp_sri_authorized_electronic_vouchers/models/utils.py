# -*- coding: utf-8 -*-

import requests

table3 = {
    '04': '04',
    '05': '05',
    '06': '06',
    '07': '07',
    '18': '01',
}

# TODO
table6 = {
    '0': '04',
    '1': '05',
    '2': '07'
}

table18 = {
    'i0': '0',
    'i': '2',
    'ni': '6'
}

table20 = {
    'rir': '1',
    'ret_iva_bie': '2',
    'ret_iva_ser': '2',
    'ret_isd': '6'
}

table21 = {
    10: '9',
    20: '10',
    30: '1',
    50: '11',
    70: '2',
    100: '3'
}

MSG_SCHEMA_INVALID = u"El sistema generó el XML pero"
" el comprobante electrónico no pasa la validación XSD del SRI."

SITE_BASE_TEST = 'https://celcer.sri.gob.ec/'
SITE_BASE = 'https://cel.sri.gob.ec/'
WS_RECEIVE_TEST = 'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl'
WS_AUTH_TEST = 'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl'
WS_RECEIVE = 'https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl'
WS_AUTH = 'https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl'

def check_service(environment='test'):
    """
    Verificamos servicio web del SRI, según especificaciones debe ser de 3 segundos (Producción)
    :param environment:
    :return:
    """
    flag = False
    if environment == 'test':
        URL = WS_RECEIVE_TEST
    else:
        URL = WS_RECEIVE
    for i in [1, 2, 3]:
        try:
            res = requests.head(URL, timeout=3)
            flag = True
        except requests.exceptions.RequestException:
            return flag, False
    return flag, res
