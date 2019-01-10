# -*- coding: utf-8 -*-

{
    'name': "Núcleo de Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'base',
        'web',
        'web_widget_colorpicker'
    ],
    'data': [
        'security/core_security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/res.country.state.csv',
        'data/canton.csv',
        'data/parish.csv',
        'views/assets.xml',
        'views/res_company_views.xml',
        'report/layout_report.xml',
        'report/paperformat_report.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
