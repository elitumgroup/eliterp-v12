# -*- coding: utf-8 -*-

{
    'name': "Notas Bancarias Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'eliterp_core',
        'eliterp_account'
    ],
    'data': [
        'data/sequences.xml',
        'security/account_bank_note_security.xml',
        'security/ir.model.access.csv',
        'views/account_bank_note_views.xml',
        'wizard/account_bank_note_cancel_views.xml',
        'report/account_bank_note_report.xml',
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
