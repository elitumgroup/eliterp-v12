# -*- coding: utf-8 -*-

{
    'name': "Gestión de compras Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'purchase',
        'eliterp_account_company_division'
    ],
    'data': [
        'views/purchase_order_views.xml',
        'views/purchase_invoice_views.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
