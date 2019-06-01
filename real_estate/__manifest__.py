# -*- coding: utf-8 -*-
{
    'name': "Real Estate",

    'summary': """
        
    """,

    'description': """
    """,

    'author': "GrowIT",
    'website': "",

    'category': 'Uncategorized',
    'version': '0.2',

    'depends': ['base', 'account'],

    'data': [
        'data/real.estate.property.type.csv',
        'data/product_data.xml',
        'data/sequence.xml',
        'security/ir.model.access.csv',
        'security/ir_security.xml',
        'views/views.xml',
        'views/report_paymentdetails_template.xml',
        'views/ir_config_settings.xml',
        'wizard/wizard.xml',
    ],
    'installable': True,
    'application': True,
}