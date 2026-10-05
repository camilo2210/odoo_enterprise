{
    'name': 'POS Self Order Mobile',
    'category': 'Hidden',
    'summary': 'Odoo Mobile POS Self Order module',
    'description': """
This module provides the POS Self Order function of the Odoo Mobile App.
        """,
    'depends': ['pos_self_order', 'pos_mobile_android'],
    'auto_install': True,
    'data': [
        'views/point_of_sale_dashboard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pos_self_order_mobile/static/src/backend/**/*',
        ],
        'pos_self_order.assets': [
            'web_mobile/static/src/js/services/core.js',
            'pos_mobile_android/static/src/app/utils/native.js',
            'pos_mobile_android/static/src/app/utils/lna_fetch.js',
            'pos_self_order_mobile/static/src/app/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
