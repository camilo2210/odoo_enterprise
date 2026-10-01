# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    account_bills_to_receive_id = fields.Many2one(
        related='company_id.account_bills_to_receive_id', readonly=False, check_company=True)
    account_bills_to_receive_active = fields.Boolean(
        related='account_bills_to_receive_id.active', string="Bills to Receive Account Active")
    account_billed_not_received_id = fields.Many2one(
        related='company_id.account_billed_not_received_id', readonly=False, check_company=True)
    account_billed_not_received_active = fields.Boolean(
        related='account_billed_not_received_id.active', string="Billed Not Received Account Active")
