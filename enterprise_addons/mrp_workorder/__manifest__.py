# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'MRP II',
    'category': 'Supply Chain/Manufacturing',
    'sequence': 51,
    'summary': """Work Orders, Planning, Stock Reports.""",
    'depends': ['quality', 'mrp', 'barcodes', 'web_gantt', 'web_tour', 'hr'],
    'auto_install': ['mrp'],
    'description': """Enterprise extension for MRP
* Work order planning.  Check planning by Gantt views grouped by production order / work center
* Traceability report
* Cost Structure report (mrp_account)""",
    'data': [
        'security/mrp_workorder_security.xml',
        'data/mrp_workorder_data.xml',
        'report/quality_check_label_templates.xml',
        'views/hr_employee_views.xml',
        'views/quality_views.xml',
        'views/mrp_bom_views.xml',
        'views/mrp_workorder_views.xml',
        'views/mrp_operation_views.xml',
        'views/mrp_production_views.xml',
        'views/mrp_workcenter_views.xml',
        'views/stock_picking_type_views.xml',
        'views/res_config_settings_view.xml',
        'views/mrp_workorder_views_menus.xml',
        'views/stock_quant_views.xml',
        'wizard/additional_workorder_views.xml',
        'wizard/mrp_production_backorder.xml',
        'wizard/propose_change_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/mrp_production_demo.xml',
        'data/mrp_workorder_demo.xml',
        'data/mrp_workorder_demo_stool.xml'
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'mrp_workorder/static/src/**/*.scss',
            'mrp_workorder/static/src/**/*.js',
            'mrp_workorder/static/src/**/*.xml',
            ('remove', 'mrp_workorder/static/src/mrp_*_gantt/*'),
        ],
        'web.assets_backend_lazy': [
            'mrp_workorder/static/src/mrp_*_gantt/*',
        ],
        'web.assets_tests': [
            'mrp_workorder/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'mrp_workorder/static/tests/**/*',
            ('remove', 'mrp_workorder/static/tests/tours/**/*'),
        ],
    }
}
