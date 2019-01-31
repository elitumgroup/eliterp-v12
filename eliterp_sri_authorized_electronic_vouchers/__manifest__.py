# -*- coding: utf-8 -*-

{
    'name': "Comprobantes autorizados electrónicos Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'mail',
        'eliterp_sri',
        'eliterp_treasury'
    ],
    'data': [
        'data/sequences.xml',
        'data/mail_template_data.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/point_printing_views.xml',
        'views/res_company_views.xml',
        'views/account_invoice_views.xml',
        'views/account_retention_views.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
