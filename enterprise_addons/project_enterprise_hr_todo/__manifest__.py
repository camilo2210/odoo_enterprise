{
    'name': "Project Enterprise HR To-Do",
    'summary': """Bridge module for project_enterprise_hr and project_todo""",
    'description': """
Bridge module for project_enterprise_hr and project_todo
    """,
    'category': 'Services/Project',
    'depends': ['project_enterprise_hr', 'project_todo'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'data/digest_data.xml',
        'data/todo_mail_alias.xml',
        'data/todo_template.xml',
    ],
}
