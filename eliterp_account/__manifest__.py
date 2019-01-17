# -*- coding: utf-8 -*-

{
    'name': "Contabilidad Eliterp",
    'summary': 'Módulo contable personalizado para la localización de Ecuador.',
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'product',
        'eliterp_core',
        'eliterp_account_template',
        'account_accountant',
        'account_cancel'
    ],
    'data': [
        'data/sequences.xml',
        'security/account_security.xml',
        'security/ir.model.access.csv',
        'views/product_views.xml',
        'views/account_views.xml',
        'views/account_bank_records_views.xml',
        'views/account_period_views.xml',
        'views/account_cancel_views.xml',
        'views/hide_menus.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
