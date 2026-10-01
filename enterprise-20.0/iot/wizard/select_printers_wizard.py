from odoo import fields, models


class SelectPrintersWizard(models.TransientModel):
    _inherit = "select.printers.wizard"

    duplex = fields.Boolean("Duplex", help="Print duplex if the printer allows it.", default=True)
    is_duplex_hidden = fields.Boolean(
        default=lambda self: self.env.context.get("report_name") != "Shipping Labels"
    )
