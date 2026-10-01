# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Certificates',
    'category': 'Productivity/Documents',
    'summary': 'Hr Skills Certificates in Documents',
    'description': """
Save uploaded certificates to documents folder of employees.
""",
    'depends': ['documents', 'hr_skills'],
    'post_init_hook': '_post_init_hook',
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
