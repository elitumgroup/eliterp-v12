# -*- coding: utf-8 -*-

{
    'name': "Requerimiento de Pago (Compras) Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'eliterp_purchase',
        'eliterp_payment_requirement'
    ],
    'data': [
        'views/purchase_views.xml',
        'views/payment_requirement_views.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
