# -*- coding: utf-8 -*-

{
    'name': "Nómina Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'hr_payroll',
        'hr_payroll_account',
        'eliterp_treasury'
    ],
    'data': [
        'data/sequences.xml',
        'security/hr_payroll_security.xml',
        'security/ir.model.access.csv',
        'report/payroll_reports.xml',
        'views/salary_advance_views.xml',
        'views/payslip_views.xml',
        'views/payslip_run_views.xml',
        'views/hide_menus.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
