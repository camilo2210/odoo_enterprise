# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Biometric Attendances",
    "category": "Human Resources/Attendances",
    "summary": "Shared biometric attendance inbox and processor",
    "depends": [
        "hr_attendance",
    ],
    "data": [
        "security/ir.access.csv",
        "views/biometric_event_views.xml",
        "views/hr_attendance_views.xml",
    ],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
