# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "PoS Pricer",
    "category": "Sales/Point of Sale",
    "sequence": 6,
    "summary": "Display and change your products information on electronic Pricer tags",
    "data": [
        "views/pos_pricer_configuration.xml",
        "data/pos_config_data.xml",
        "security/ir.access.csv",
    ],
    "auto_install": True,
    "depends": ["pricer", "point_of_sale"],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
