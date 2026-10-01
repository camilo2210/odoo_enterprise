
{
    'name': 'Web Cohort Tests',
    'category': 'Hidden',
    'sequence': 9876,
    'summary': 'Web cohort Test',
    'description': """This module contains tests related to web cohort. Those are
present in a separate module as it contains models used only to perform
tests independently to functional aspects of other models. """,
    'depends': ['web_cohort'],
    'data': [
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
