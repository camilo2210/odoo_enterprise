# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Planning and Attendances",
    "category": "Hidden",
    "sequence": 50,
    "summary": "Compare plannings and attendances",
    "depends": ["planning", "hr_attendance"],
    "description": """
Compare plannings and attendances
=================================
Allow users to compare planned hours vs. the hours effectively done in attendance.
""",
    "data": [
        "report/planning_attendance_analysis_report_views.xml",
        "views/planning_attendance_menus.xml",
        'security/ir.access.csv',
    ],
    "auto_install": True,
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
