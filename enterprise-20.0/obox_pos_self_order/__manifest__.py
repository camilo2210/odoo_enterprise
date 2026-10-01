{
    'name': 'PoS Self Order & Obox',
    'category': 'Administration/IoT',
    'depends': ['obox_point_of_sale', 'pos_self_order'],
    'description': "Link between Obox and PoS self order",
    'auto_install': True,
    'data': [
        'views/pos_printer_views.xml',
    ],
    'assets': {
        "pos_self_order.assets": [
            'obox_point_of_sale/static/src/app/utils/obox_proxy.js',
            'obox_point_of_sale/static/src/app/plugins/pos_ticket_printer_plugin.js',
        ],
        "pos_self_order.assets_tests": [
            'obox_pos_self_order/static/tests/tours/self_order_obox_tour.js',
        ],
        'web.assets_tests': [
            'obox_pos_self_order/static/tests/tours/self_order_obox_pos_tour.js',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
