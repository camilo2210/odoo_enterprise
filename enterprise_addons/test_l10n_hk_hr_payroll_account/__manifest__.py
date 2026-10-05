# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Test Hong Kong Payroll',
    'category': 'Human Resources',
    'summary': 'Test Hong Kong Payroll',
    'depends': [
        'l10n_hk_hr_payroll_account',
        'documents_l10n_hk_hr_payroll',
        'hr_payroll_attendance',
    ],
    'other_files': [
        'data/expected_xmls/ir56b.xml',
        'data/expected_xmls/ir56e.xml',
        'data/expected_xmls/ir56f.xml',
        'data/expected_xmls/ir56g.xml',
        'data/expected_xmls/ir56m.xml',
        'data/expected_xmls/ir56f_with_termination.xml',
    ],
    'author': 'Odoo S.A.',
    'post_init_hook': 'generate_payslips',
    'license': 'OEEL-1',
}
