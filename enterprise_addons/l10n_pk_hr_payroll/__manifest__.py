# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Pakistan - Payroll',
    'countries': ['pk'],
    'category': 'Human Resources/Payroll',
    'description': """
Pakistan Payroll and End of Service rules
=========================================
- Basic salaries calculations.
- Tax bracket calculations/deductions
    """,
    'depends': ['hr_payroll'],
    'auto_install': ['hr_payroll'],
    'data': [
        'data/resource_calendar_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_work_entry_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_rule_parameter_data.xml',
        'wizard/hr_payslip_pk_ytd_adjustment_wizard_views.xml',
        'views/hr_payslip_views.xml',
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'demo':[
        'data/l10n_pk_hr_payroll_demo.xml'
    ],
    'post_init_hook': '_l10n_pk_hr_payroll_post_install',
}
