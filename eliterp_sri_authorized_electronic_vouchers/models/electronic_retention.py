# -*- coding: utf-8 -*-

import os
import time
import logging
import itertools
from jinja2 import Environment, FileSystemLoader
from odoo import api, models, fields
from odoo.exceptions import UserError
from . import utils
from ..xades.sri import DocumentXML
from ..xades.xades import Xades


class Retention(models.Model):
    _name = 'account.retention'
    _inherit = ['account.retention', 'sri.electronic.vouchers']
    _logger = logging.getLogger('sri.electronic.vouchers')
    TEMPLATES = {
        'out_retention': 'out_retention.xml'
    }

    authorization = fields.Char('Nº Autorización', readonly=True, size=49,
                                states={'draft': [('readonly', False)]})
