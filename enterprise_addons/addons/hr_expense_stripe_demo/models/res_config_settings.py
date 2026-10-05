from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_create_stripe_demo_account(self):
        return self.company_id.action_create_stripe_demo_account()
