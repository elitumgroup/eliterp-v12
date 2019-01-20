# -*- coding: utf-8 -*-

{
    'name': "Reportes Contables Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'eliterp_account',
        'eliterp_treasury'
    ],
    'data': [
        'wizard/accounting_reports_wizard_views.xml',
        'views/accounting_reports_views.xml',
        'report/accounting_reports.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
