# -*- coding: utf-8 -*-

import os
import subprocess
import logging

class CheckDigit(object):
    """
    Definición de módulo 11
    """
    _MODULE_11 = {
        'BASE': 11,
        'FACTOR': 2,
        'RETURN11': 0,
        'RETURN10': 1,
        'WEIGHT': 2,
        'MAX_WEIGHT': 7
    }

    @classmethod
    def _eval_mod11(self, module):
        if module == self._MODULE_11['BASE']:
            return self._MODULE_11['RETURN11']
        elif module == self._MODULE_11['BASE'] - 1:
            return self._MODULE_11['RETURN10']
        else:
            return module

    @classmethod
    def compute_mod11(self, data):
        """
        Cálculo de módulo 11
        :param data:
        :return:
        """
        total = 0
        weight = self._MODULE_11['WEIGHT']

        for item in reversed(data):
            total += int(item) * weight
            weight += 1
            if weight > self._MODULE_11['MAX_WEIGHT']:
                weight = self._MODULE_11['WEIGHT']
        mod = 11 - total % self._MODULE_11['BASE']
        mod = self._eval_mod11(mod)
        return mod


class Xades(object):

    def sign(self, xml_name, file_pk12, password):
        """
        Método que aplica la firma digital al documento XML
        :param xml_name:
        :param file_pk12:
        :param password:
        :return:
        """
        JAR_PATH = 'signature/signature.jar'
        JAVA_CMD = 'java'
        signature_path = os.path.join(os.path.dirname(__file__), JAR_PATH)
        command = [
            JAVA_CMD,
            '-jar',
            signature_path,
            file_pk12,
            password,
            '/home/odoo/Documents/generated/generated-%s' % xml_name + '.xml',
            '/home/odoo/Documents/signed',
            'signed-%s.xml' % xml_name
        ]
        path_file = '/home/odoo/Documents/signed/' + 'signed-%s.xml' % xml_name
        try:
            logging.info('Probando comando de firma digital...')
            subprocess.check_output(command)
        except subprocess.CalledProcessError as e:
            logging.error('Llamada a proceso JAVA con código: %s' % e.returncode)
            logging.error('Error: %s' % e.output)
        xml_string = open(path_file, 'r').read()
        return xml_string