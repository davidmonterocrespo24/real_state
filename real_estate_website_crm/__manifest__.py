# -*- coding: utf-8 -*-
{
    'name': "Real Estate - Website",

    'summary': """
        Publish Property on Website
    """,

    'description': """
    """,

    'author': "GrowIt",
    'website': "",

    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base', 'real_estate', 'website'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'data/data.xml',
    ],
    # only loaded in demonstration mode
}