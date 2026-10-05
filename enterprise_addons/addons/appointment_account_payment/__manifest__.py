# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Pay to Book',
    'category': 'Marketing/Online Appointment',
    'summary': 'Up-front payment on bookings',
    'description': """Add a payment step at the end of appointment and resource bookings""",
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
    'depends': ['appointment', 'account_payment'],
    'data': [
        'views/appointment_answer_input_views.xml',
        'views/appointment_templates_appointments.xml',
        'views/appointment_templates_payment.xml',
        'views/appointment_templates_registration.xml',
        'views/appointment_templates_validation.xml',
        'views/appointment_type_views.xml',
        'views/calendar_booking_templates.xml',
        'views/calendar_booking_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/product_demo.xml',
        'data/appointment_demo.xml',
        'data/calendar_event_demo.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'appointment_account_payment/static/src/scss/appointment_payment.scss',
        ],
    }
}
