# -*- coding: utf-8 -*-

{
    'name': "Ventas Eliterp",
    'author': "Ranzaweb",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'sale_management',
        'mail'
    ],
    'data': [
        'security/sale_security.xml',
        'security/ir.model.access.csv',
        'views/sale_shop_views.xml',
        'views/sale_order_views.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
