# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Employees in Mobile',
    'category': 'Human Resources/Employees',
    'summary': 'Employees in Mobile',
    'description': """ """,
    'depends': ['hr', 'web_mobile'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'hr_mobile/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'hr_mobile/static/tests/**/*.test.js',
        ],
    }
}
