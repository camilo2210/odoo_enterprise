# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Timesheets - AI",
    "summary": "Extend the Timesheet Assistant with AI-powered features",
    "depends": ["timesheet_grid", "ai"],
    "category": "Services/Timesheets",
    "auto_install": True,
    "data": [
        "data/ai_composer_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ai_timesheet_grid/static/src/**/*",
        ],
    },
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
