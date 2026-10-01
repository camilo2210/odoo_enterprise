# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_in_gstr_gst_username = fields.Char(string="GST User Name (IN)", groups="base.group_system")
    l10n_in_gstr_gst_token = fields.Char(string="GST Token (IN)", groups="base.group_system")
    l10n_in_gstr_gst_token_validity = fields.Datetime(string="GST Token (IN) Valid Until", groups="base.group_system")
    l10n_in_gstr_activate_einvoice_fetch = fields.Selection(
        string='Fetch Vendor E-Invoiced Documents',
        selection=[
            ('manual', 'Fetch Manually'),
            ('automatic', 'Fetch Automatically'),
        ],
        default='manual',
        help="""
            Fetch Manually - Invoices are created without lines but an IRN number, but there is a button to get the lines.
            Fetch Automatically - Existing documents with an IRN are automatically updated, and incoming documents are fetched and populated automatically."""
    )
    l10n_in_gst_efiling_feature = fields.Boolean(string="GST E-Filing & Matching Feature")
    l10n_in_fetch_vendor_edi_feature = fields.Boolean(string="Fetch Vendor E-Invoiced Document")
    l10n_in_enet_vendor_batch_payment_feature = fields.Boolean(string="ENet Vendor Batch Payment")

    def _is_l10n_in_gstr_token_valid(self):
        self.ensure_one()
        return (
            self.sudo().l10n_in_gstr_gst_token_validity
            and self.sudo().l10n_in_gstr_gst_token_validity > fields.Datetime.now()
        )

    def write(self, vals):
        res = super().write(vals)
        if set(vals) & {'account_return_periodicity', 'account_fiscal_country_id', 'l10n_in_gst_registration_type'}:
            iff_return_type = self.env.ref('l10n_in_reports.in_gstr_iff_return_type', raise_if_not_found=False)
            if iff_return_type:
                for company in self:
                    is_iff_applicable = (
                        company.account_fiscal_country_id.code == 'IN'
                        and company.account_return_periodicity == 'trimester'
                        and company.l10n_in_gst_registration_type == 'regular'
                    )
                    iff_return_type.with_context(propagate_active_to_report=True).active = is_iff_applicable
        return res
