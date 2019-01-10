# -*- coding: utf-8 -*-

{
    'name': "Proyecto Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'eliterp_account_company_division'
    ],
    'data': [
        'security/account_project_security.xml',
        'security/ir.model.access.csv',
        'views/account_project_views.xml',
        'views/account_invoice_views.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
