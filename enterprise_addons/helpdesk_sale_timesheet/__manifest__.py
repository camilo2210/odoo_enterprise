# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sell Helpdesk Timesheet',
    'category': 'Services/Helpdesk',
    'summary': 'Project, Helpdesk, Timesheet and Sale Orders',
    'depends': ['helpdesk_timesheet', 'sale_timesheet_enterprise', 'helpdesk_sale'],
    'description': """
        Bill timesheets logged on helpdesk tickets.
    """,
    'auto_install': True,
    'data': [
        'views/account_analytic_line_views.xml',
        'views/helpdesk_team_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/helpdesk_portal_templates.xml',
        'views/project_project_views.xml',
        'views/sale_order_views.xml',
        'report/helpdesk_ticket_analysis_views.xml',
        'report/helpdesk_sla_analysis_views.xml',
        'report/helpdesk_sale_timesheet_report.xml',
        'security/ir.access.csv',
    ],
    'demo': ['data/helpdesk_sale_timesheet_demo.xml'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_helpdesk_sale_timesheet_post_init'
}
