# -*- coding: utf-8 -*-

{
    'name': "Reportes Tesorería Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'report_xlsx',
        'eliterp_accounting_reports'
    ],
    'data': [
        'wizard/treasury_reports_wizard_views.xml',
        'views/treasury_reports_views.xml',
        'report/treasury_reports.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
