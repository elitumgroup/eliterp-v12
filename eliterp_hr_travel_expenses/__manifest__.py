# -*- coding: utf-8 -*-

{
    'name': "Viáticos Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'mail',
        'eliterp_hr_employee',
        'eliterp_start',
        'eliterp_treasury'
    ],
    'data': [
        'data/sequences.xml',
        'security/hr_travel_expenses_security.xml',
        'security/ir.model.access.csv',
        'views/hr_travel_expenses_views.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
