# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Planning - Skills',
    'summary': 'Planning Skills',
    'description': """
Search planning slots by skill
    """,
    'category': 'Human Resources/Planning',
    'depends': ['planning', 'hr_skills'],
    'auto_install': True,
    'data': [
        'views/planning_slot_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
