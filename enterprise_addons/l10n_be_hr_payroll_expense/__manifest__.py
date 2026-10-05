# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Belgian Payroll - Mobility Budget Expenses",
    "category": "Human Resources/Payroll",
    "summary": "Mobility budget management for Belgian payroll expenses",
    "description": """
Bridge module between l10n_be_hr_payroll and hr_payroll_expense for mobility budget management.

Features:
- Mobility budget period tracking on hr.version
- Configuration of mobility expense categories on company
- Budget tracking banner on mobility expenses
    """,
    "depends": ["l10n_be_hr_payroll", "hr_payroll_expense"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/hr_expense_views.xml",
    ],
    "auto_install": True,
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
