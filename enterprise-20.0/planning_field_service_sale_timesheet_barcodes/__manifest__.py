{
    'name': 'Field Service - Barcode',
    'category': 'Human Resources/Planning',
    'summary': 'Scan barcodes to add products to interventions',
    'depends': ['planning_field_service_sale_timesheet', 'barcodes'],
    'assets': {
        'web.assets_backend': [
            'planning_field_service_sale_timesheet_barcodes/static/src/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
