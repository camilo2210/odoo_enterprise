# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Sale Commission',
    'category': 'Sales/Commission',
    'sequence': 105,
    'summary': "Manage your salespersons' commissions",
    'description': """
    """,
    'depends': ['sale_management'],
    'data': [
        'wizard/sale_commission_add_multiple_user.xml',
        'wizard/sale_commission_plan_duplicated_users_wizard_views.xml',
        'views/sale_commission_plan_view.xml',
        'views/sale_commission_achievement_view.xml',
        'report/commission_report.xml',
        'report/achievement_report.xml',
        'views/sale_commission_menu.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/sale_commission_demo.xml'
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'sale_commission/static/src/js/commission_plan_graph/commission_plan_graph.js',
            'sale_commission/static/src/js/commission_plan_graph/commission_plan_graph.scss',
            'sale_commission/static/src/js/commission_plan_graph/commission_plan_graph.xml',
            'sale_commission/static/src/js/commission_plan_list_renderer/commission_plan_list_renderer.js',
            'sale_commission/static/src/js/commission_plan_list_renderer/commission_plan_empty_screen.xml',
            'sale_commission/static/src/scss/commission_plan_empty_screen.scss',
        ],
    }
}
