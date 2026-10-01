{
    'name': 'Annual Reports',
    'summary': 'Create Annual Reports with Knowledge',
    'depends': [
        'accountant',
        'knowledge',
    ],
    'data': [
        'report/reports.xml',
        'views/audit_report_views.xml',
        'views/knowledge_article_views.xml',
        'views/menuitems.xml',
        'data/knowledge_article_template_category_data.xml',
        'data/knowledge_article_template_data.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'accountant_knowledge/static/src/actions/**/*',
            'accountant_knowledge/static/src/components/**/*',
            'accountant_knowledge/static/src/editor/**/*',
            'accountant_knowledge/static/src/scss/**/*',
            'accountant_knowledge/static/src/views/**/*',
        ],
        'web.assets_frontend': [
            'accountant_knowledge/static/src/editor/embedded_components/core/**/*',
            'accountant_knowledge/static/src/public/**/*',
        ],
        'web.report_assets_pdf': [
            'accountant_knowledge/static/report/reports.scss',
        ],
    },
}
