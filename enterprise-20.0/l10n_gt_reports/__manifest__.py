# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'author': 'Odoo S.A.',
    'name': 'Guatemala - Accounting Reports',
    'icon': '/account/static/description/l10n.png',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Libro de Ventas and Libro de Compras (VAT books) for Guatemala',
    'description': """
Guatemala VAT books (SAT)
=========================

Adds the two legally required VAT books as Tax Report variants:

- **Libro de Ventas** (Sales Book)
- **Libro de Compras y Servicios Recibidos** (Purchase Book)

Reviewable by period and exportable to PDF (legal output) and CSV.
    """,
    'website': 'https://www.odoo.com/documentation/latest/applications/finance/fiscal_localizations.html',
    'depends': [
        'l10n_gt_edi',
        'account_reports',
    ],
    'data': [
        'data/account_libro_report.xml',
        'report/l10n_gt_libro_pdf.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_gt_reports/static/src/components/**/*',
        ],
        # Loaded only when wkhtmltopdf renders the report, so it styles the PDF, not the live view.
        'account_reports.assets_pdf_export': [
            'l10n_gt_reports/static/src/scss/pdf_l10n_gt_libro.scss',
        ],
    },
    'auto_install': True,
    'license': 'OEEL-1',
}
