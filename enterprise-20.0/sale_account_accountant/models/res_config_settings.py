# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    account_invoices_to_issue_id = fields.Many2one(
        related='company_id.account_invoices_to_issue_id', readonly=False, check_company=True)
    account_invoices_to_issue_active = fields.Boolean(
        related='account_invoices_to_issue_id.active', string="Invoices to be Issued Account Active")
    account_invoiced_not_delivered_id = fields.Many2one(
        related='company_id.account_invoiced_not_delivered_id', readonly=False, check_company=True)
    account_invoiced_not_delivered_active = fields.Boolean(
        related='account_invoiced_not_delivered_id.active', string="Invoiced Not Delivered Account Active")
