# -*- coding: utf-8 -*-

{
    'name': "Cheques Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'eliterp_treasury',
        'account_check_printing'
    ],
    'data': [
        'security/account_checks_security.xml',
        'security/ir.model.access.csv',
        'wizard/report.xml',
        'views/account_journal_views.xml',
        'views/account_checks_views.xml',
        'views/account_voucher_views.xml',
        'views/account_bank_records_views.xml',
        'views/hide_menus.xml',
        'report/report_template.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
