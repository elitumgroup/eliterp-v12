# -*- coding: utf-8 -*-

{
    'name': "Tesorería Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'eliterp_sri',
        'account_voucher'
    ],
    'data': [
        'data/sequences.xml',
        'security/treasury_security.xml',
        'security/ir.model.access.csv',
        'report/voucher_reports.xml',
        'views/treasury_views.xml',
        'views/account_retention_views.xml',
        'views/account_voucher_views.xml',
        'views/account_pay_order_views.xml',
        'views/account_invoice_views.xml',
        'wizard/account_voucher_cancel_views.xml',
        'views/hide_menus.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
