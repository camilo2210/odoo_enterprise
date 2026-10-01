# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    invoice_consolidation = fields.Boolean(
        string="Consolidate subscriptions billing",
        help="Consolidate all of a customer's subscriptions that are due to be billed on the same day onto a single invoice.",
        config_parameter='sale_subscription.invoice_consolidation',
    )
    payment_failed_reminder_days = fields.Char(
        string="Payment failure reminder days",
        help="Comma-separated list of days after the invoice date (e.g. 2,7,14) on which a "
            "reminder email is sent when an automatic payment with a saved token fails.",
        config_parameter='sale_subscription.payment_failed_reminder_days',
    )
    no_token_reminder_days = fields.Char(
        string="No-token payment reminder days",
        help="Comma-separated list of day offsets relative to the next invoice date "
            "(e.g. 0,1,2,7,14,-2,-7,-14) on which a payment reminder is sent for subscriptions with no saved payment token.",
        config_parameter='sale_subscription.no_token_reminder_days',
    )
