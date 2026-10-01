# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Coupons & Loyalty",
    "summary": "Use discounts, gift cards, eWallets and loyalty programs in your sales channels",
    "category": "Loyalty in Marketing Automation",
    "depends": ["marketing_automation", "loyalty"],
    "data": [
        "security/ir.access.csv",
        "views/marketing_activity_views.xml",
        "views/marketing_campaign_views.xml",
    ],
    "assets": {
        'web.assets_backend': [
            "marketing_automation_loyalty/static/**/*",
        ]
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
