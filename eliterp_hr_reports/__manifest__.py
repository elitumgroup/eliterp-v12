# -*- coding: utf-8 -*-

{
    'name': "Reportes RRHH Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'eliterp_hr_employee',
        'eliterp_hr_payroll'
    ],
    'data': [
        'wizard/hr_reports_wizard_views.xml',
        'views/hr_reports_views.xml',
        'report/hr_reports.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
