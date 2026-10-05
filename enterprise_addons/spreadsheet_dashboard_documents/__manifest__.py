# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Spreadsheet Documents",
    "category": "Productivity/Documents",
    "summary": "Spreadsheet Documents",
    "description": "Spreadsheet Documents",
    "depends": ["spreadsheet_dashboard_edition", "documents_spreadsheet"],
    "data": [
        "wizard/documents_to_dashboard_views.xml",
        'security/ir.access.csv',
    ],
    "auto_install": True,
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "assets": {
        "spreadsheet.o_spreadsheet": [
            (
                "after",
                "spreadsheet/static/src/o_spreadsheet/o_spreadsheet.js",
                "spreadsheet_dashboard_documents/static/src/bundle/**/*.js",
            ),
        ],
        'web.assets_unit_tests': [
            "spreadsheet_dashboard_documents/static/tests/**/*.js",
        ],
    },
}
