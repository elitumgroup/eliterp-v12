# -*- coding: utf-8 -*-

{
    'name': "Caja chica Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'mail',
        'eliterp_treasury'
    ],
    'data': [
        'data/sequences.xml',
        'security/account_small_box_security.xml',
        'security/ir.model.access.csv',
        'report/small_box_reports.xml',
        'views/small_box_views.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
