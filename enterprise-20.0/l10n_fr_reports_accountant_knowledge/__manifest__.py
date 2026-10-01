{
    'name': 'France - Accountant Knowledge',
    'summary': 'French Annual Report template for the Knowledge app',
    'description': """
Adds the "Annual Template FR" Knowledge template, built on the models of documents
de synthèse defined in Livre III of the PCG (règlement ANC n° 2014-03) :

- the French balance sheet and income statement models (Titre VIII, Chapitre II) ;
- the full content of the annex to the annual accounts (Titre VIII, Chapitre III) ;
- the financing table (Titre IX).
    """,
    'category': 'Accounting/Localizations',
    'depends': [
        'l10n_fr_reports',
        'accountant_knowledge',
    ],
    'data': [
        'data/knowledge_article_template_fr_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
