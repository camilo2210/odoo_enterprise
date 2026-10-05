from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    intercompany_generate_sales_orders = fields.Boolean(
        string="Generate Sales Orders",
        help="If another company confirms a Purchase Order with this company, a Sales Order will be created with the chosen warehouse based on the contact address for the delivery of goods."
    )
    intercompany_generate_purchase_orders = fields.Boolean(
        string="Generate Purchase Orders",
        help="If another company confirms a Sales Order with this company, a Purchase Order will be created with the chosen warehouse based on the contact address for the receipt of goods."
    )
