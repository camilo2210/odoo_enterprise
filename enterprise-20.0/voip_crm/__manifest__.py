{  # noqa: B018
    "name": "Phone - CRM",
    "summary": "Phone integration with CRM module.",
    "description": "Add CRM leads to your activity queue.",
    "category": "Sales/CRM",
    "depends": ["crm", "voip"],
    "auto_install": True,
    "data": [
        "views/crm_lead_views.xml",
        "views/voip_call_views.xml",
        "wizards/mail_activity_schedule_views.xml",
        'security/ir.access.csv',
    ],
    "demo": [
        "demo/voip_call.xml",
    ],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "assets": {
        "im_livechat.assets_embed_core": [
            "voip_crm/static/src/core/common/**/*",
        ],
        "mail.assets_public": [
            "voip_crm/static/src/core/common/**/*",
        ],
        "portal.assets_chatter_helpers": [
            "voip_crm/static/src/core/common/**/*",
        ],
        "web.assets_backend": [
            "voip_crm/static/src/**/*",
        ],
        "web.assets_unit_tests": [
            "voip_crm/static/tests/**/*",
        ],
    },
}
