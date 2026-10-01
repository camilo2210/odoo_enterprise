{
    'name': 'Appointment Google Reserve',
    'category': 'Productivity',
    'description': """Enable a link between your appointment type and the google API""",
    'depends': [
        'appointment',
        'iap',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'data/ir_cron_data.xml',
        'views/appointment_type_views.xml',
        'views/google_reserve_merchant_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/google_reserve_demo.xml',
    ],
}
