# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Salary Configurator (United Arab Emirates)',
    'category': 'Human Resources',
    'summary': 'Salary Package Configurator',
    'depends': [
        'hr_contract_salary',
        'l10n_ae_hr_payroll',
    ],
    'data': [
        'data/hr_contract_salary_benefit_data.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
