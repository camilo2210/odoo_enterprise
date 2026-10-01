# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_hr_payroll_account_iso20022 = fields.Boolean(string='Payroll with SEPA payment')
    ytd_reset_day = fields.Integer(related="company_id.ytd_reset_day", readonly=False)
    ytd_reset_month = fields.Selection(related="company_id.ytd_reset_month", readonly=False)
    payslip_generate_and_send_trigger = fields.Selection(
        related="company_id.payslip_generate_and_send_trigger", readonly=False
    )
    deferred_time_off_manager = fields.Many2one(
        'res.users', related='company_id.deferred_time_off_manager', check_company=True, readonly=False)
    first_payrun_date = fields.Date(related='company_id.first_payrun_date', readonly=False)
    payroll_closing_date = fields.Selection(related='company_id.payroll_closing_date', readonly=False)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    @api.model_create_multi
    def create(self, vals_list):
        # Amazing workaround: non-stored related fields on company are a BAD idea since the 2 fields
        # must follow the constraint '_check_ytd_reset_day'. The thing is, in case of related
        # fields, the inverse write is done one value at a time, and thus the constraint is verified
        # one value at a time... so it is likely to fail.
        for vals in vals_list:
            ytd_reset_day = vals.pop('ytd_reset_day', False) or self.env.company.ytd_reset_day
            ytd_reset_month = vals.pop('ytd_reset_month', False) or self.env.company.ytd_reset_month
            vals = {}
            if ytd_reset_day != self.env.company.ytd_reset_day:
                vals['ytd_reset_day'] = ytd_reset_day
            if ytd_reset_month != self.env.company.ytd_reset_month:
                vals['ytd_reset_month'] = ytd_reset_month
            if vals:
                self.env.company.write(vals)
        return super().create(vals_list)
