#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    l10n_be_display_eco_voucher_button = fields.Boolean(
        compute='_compute_l10n_be_display_eco_voucher_button')
    l10n_be_display_flexi_button = fields.Boolean(
        compute='_compute_l10n_be_display_flexi_button')
    l10n_be_withholding_taxes = fields.Monetary(
        compute='_compute_l10n_be_payrun_kpi'
    )

    l10n_be_onns_contribution = fields.Monetary(
        compute='_compute_l10n_be_payrun_kpi'
    )

    @api.depends('slip_ids')
    def _compute_l10n_be_display_eco_voucher_button(self):
        # Display button if batch is from belgium with out
        # employees
        for batch in self:
            should_display = batch.company_id.country_id.code == "BE" and any(
                slip.state != 'cancel' and sum(slip.line_ids.filtered(lambda l: l.code == 'ECOVOUCHERS').mapped('total')) > 0
                for slip in batch.slip_ids
            )
            batch.l10n_be_display_eco_voucher_button = should_display

    @api.depends('slip_ids.l10n_be_needs_flxwage_declaration', 'slip_ids.state')
    def _compute_l10n_be_display_flexi_button(self):
        for payrun in self:
            payrun.l10n_be_display_flexi_button = payrun.company_id.country_id.code == 'BE' and any(
                slip.l10n_be_needs_flxwage_declaration
                and slip.state in ('validated', 'paid')
                for slip in payrun.slip_ids
            )

    def _get_valid_versions(self, date_start=None, date_end=None, structure_id=None, company_id=None, employee_type_ids=None, employee_ids=None):
        valid_versions = super()._get_valid_versions(date_start, date_end, structure_id, company_id, employee_type_ids, employee_ids)
        if self.country_code != 'BE':
            return valid_versions
        non_concurrent_versions = self.env["hr.version"]
        seen_keys = set()
        for version in valid_versions:
            key = version._get_version_lookup_key()
            if key not in seen_keys:
                seen_keys.add(key)
                non_concurrent_versions |= version
        return non_concurrent_versions

    @api.depends('slip_ids.l10n_be_onss_contribution', 'slip_ids.l10n_be_withholding_taxes', 'slip_ids.state')
    def _compute_l10n_be_payrun_kpi(self):
        for payrun in self:
            not_cancelled_payslips = payrun.slip_ids.filtered_domain([['state', '!=', 'cancel']])
            payrun.l10n_be_onns_contribution = sum(
                payslip.l10n_be_onss_contribution for payslip in not_cancelled_payslips
            )
            payrun.l10n_be_withholding_taxes = sum(
                payslip.l10n_be_withholding_taxes for payslip in not_cancelled_payslips
            )

    def _get_valid_versions_domain_payrun(self, date_start=None, date_end=None, structure_id=None, company_id=None, employee_type_ids=None):
        version_domain = super()._get_valid_versions_domain_payrun(date_start, date_end, structure_id, company_id, employee_type_ids)
        profit_sharing_bonus_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_profit_sharing_bonus', raise_if_not_found=False)
        if profit_sharing_bonus_structure and structure_id == profit_sharing_bonus_structure.id:
            # Exclude JC999 employees
            jc_999 = self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_999', raise_if_not_found=False)
            if jc_999:
                version_domain &= Domain([('l10n_be_joint_committee_id', '!=', jc_999.id)])
        return version_domain

    def _generate_payslips(self):
        new_payslips = super()._generate_payslips()
        new_payslips._l10n_be_generate_termination_documents(payslip_run=self)
        return new_payslips

    def action_l10n_be_eco_vouchers(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window']._for_xml_id('l10n_be_hr_payroll.l10n_be_eco_vouchers_wizard_action')
        res['context'] = {
            'batch_id': self.id,
        }
        return res

    def action_create_and_show_flxwage_declaration(self):
        return self.slip_ids.action_create_show_flxwage_declaration()
