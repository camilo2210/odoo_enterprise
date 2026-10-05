{
    'name': 'Spreadsheet dashboard for timesheets',
    'category': 'Productivity/Dashboard',
    'summary': 'Analyze billing targets vs actual billable time in timesheets (Spreadsheet) dashboard',
    'depends': ['spreadsheet_dashboard_sale_timesheet', 'sale_timesheet_enterprise'],
    'data': [
        'data/dashboards.xml',
    ],
    'auto_install': ['sale_timesheet_enterprise'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1'
}
