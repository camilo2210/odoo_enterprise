{
    "name": "Attendances ZKTeco BioTime",
    "category": "Human Resources",
    "summary": "Integrate Zkteco BioPro with attendances app via BioTime 8.5 & 9.0 API",
    "depends": [
        "hr_attendance",
        "mail",
    ],
    "data": [
        "data/ir_cron_data.xml",
        "views/res_config_settings_view.xml",
        "views/hr_employee_views.xml",
        "views/zkteco_terminal_views.xml",
        "views/zkteco_transactions_views.xml",
        "views/hr_attendance_views.xml",
        'security/ir.access.csv',
    ],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
