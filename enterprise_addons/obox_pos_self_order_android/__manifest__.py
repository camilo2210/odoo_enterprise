{
    'name': 'PoS Self Order & Obox Android',
    'category': 'Hidden',
    'depends': ['obox_pos_self_order', 'obox_point_of_sale_android'],
    'description': "Obox Kiosk support in the Odoo Android app",
    'auto_install': True,
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
