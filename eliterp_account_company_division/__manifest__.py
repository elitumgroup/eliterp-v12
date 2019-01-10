# -*- coding: utf-8 -*-

{
    'name': "División de Compañía Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'mail',
        'eliterp_account'
    ],
    'data': [
        'security/account_company_division_security.xml',
        'security/ir.model.access.csv',
        'views/account_company_division_views.xml',
        'views/account_invoice_views.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
