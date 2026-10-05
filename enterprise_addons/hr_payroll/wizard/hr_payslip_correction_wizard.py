# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Command, Domain
from odoo.tools.misc import format_date


class HrPayslipCorrectionWizard(models.TransientModel):
    _name = "hr.payslip.correction.wizard"
    _description = "Payslip Correction Wizard"

    employee_ids = fields.Many2many("hr.employee", string="Employee", required=True,
                                   help="The employee for whom the payslip correction is being made.")
    payslip_ids = fields.Many2many("hr.payslip", string="Payslips", required=True)
    allowed_payslip_ids = fields.Many2many("hr.payslip", string="allowed_payslips", compute="_compute_allowed_payslip_ids")
    payslip_count = fields.Integer(string="Payslip Count", compute="_compute_payslips_count")
    is_multi_payslip = fields.Boolean(string="Multiple Payslips", compute="_compute_payslips_count")
    is_button_action = fields.Boolean(string="Is triggered from button", store=False)
    correction_choice = fields.Selection(
        selection=[
            ('single', 'Correct this payslip only'),
            ('multi', 'Correct all affected payslips'),
        ],
        string="Correction Choice",
        required=True,
        default='single',
        help="Choose whether to correct only the selected payslip or all payslips affected by the changes in this version.",
    )

    @api.depends("employee_ids")
    def _compute_allowed_payslip_ids(self):
        for wizard in self:
            payslips = wizard.env['hr.payslip'].search(Domain.AND([
                Domain('employee_id', 'in', wizard.employee_ids.ids),
                Domain('state', 'in', ['validated', 'paid']),
                Domain('keep_wrong_version', '=', False),
                Domain('is_refund_payslip', '=', False),
                Domain('is_refunded', '=', False),
                Domain('is_corrected', '=', False),
            ]), order="date_from")
            wizard.allowed_payslip_ids = payslips.filtered(lambda p: p.is_wrong_version or p.has_wrong_data or p.has_wrong_leaves or p.is_wrong_company_version or p.has_wrong_company_data)

    @api.depends("payslip_ids")
    def _compute_payslips_count(self):
        for wizard in self:
            wizard.payslip_count = len(wizard.allowed_payslip_ids)
            wizard.is_multi_payslip = wizard.payslip_count > 1

    def _create_payslip_runs(self, payslips, run_type):
        self.ensure_one()
        payruns = []
        for (struct, company), slips in payslips.grouped(lambda slip: (slip.struct_id, slip.company_id)).items():
            date_start = min(slips.mapped('date_from'))
            date_end = max(slips.mapped('date_to'))
            start_str = format_date(self.env, date_start, date_format="MM/yy")
            end_str = format_date(self.env, date_end, date_format="MM/yy")
            date_range = start_str if start_str == end_str else f"{start_str} -> {end_str}"
            payrun_name = self.env._("%(type)s (%(date_range)s) %(struct)s") % {
                'type': self.env._('Correction') if run_type == 'correction' else self.env._('Revert'),
                'date_range': date_range,
                'struct': struct.name,
            }
            payruns.append({
                'name': payrun_name,
                'structure_id': struct.id,
                'company_id': company.id,
                'date_start': date_start,
                'date_end': date_end,
                'slip_ids': [Command.set(slips.ids)],
            })
        self.env['hr.payslip.run'].create(payruns)

    def action_revert_payslips(self):
        self.ensure_one()
        payslips = self.payslip_ids if self.correction_choice == 'single' else self.allowed_payslip_ids
        refunds = payslips._action_refund_payslips()
        self._create_payslip_runs(refunds, 'revert')
        return refunds._get_payslips_action()

    def action_correct_payslips(self):
        self.ensure_one()
        payslips = self.payslip_ids if self.correction_choice == 'single' else self.allowed_payslip_ids
        refunds = payslips._action_refund_payslips()
        corrections = payslips._action_correct_payslips()
        self._create_payslip_runs((refunds | corrections), 'correction')
        return (refunds | corrections)._get_payslips_action()

    def action_show_related_payslips(self):
        return self.allowed_payslip_ids._get_payslips_action()

    def action_keep_wrong_version(self):
        self.ensure_one()
        if self.correction_choice == 'single':
            self.payslip_ids.keep_wrong_version = True
        else:
            self.allowed_payslip_ids.keep_wrong_version = True
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}
