# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models

ACCOUNT_DOMAIN = [('account_type', 'not in', ('asset_receivable', 'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance'))]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_stock_open_valued_locations(self):
        action = self.env["ir.actions.actions"]._for_xml_id('stock.action_prod_inv_location_form')
        action['context'] = {
            'search_default_inventory': 1,
            'search_default_prod_inv_location': 1,
        }
        return action
