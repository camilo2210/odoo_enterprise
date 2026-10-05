# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrSalaryRule(models.Model):
    _name = 'hr.salary.rule'
    _inherit = 'hr.salary.rule'

    l10n_be_joint_committee_ids = fields.Many2many(
        comodel_name='l10n.be.joint.committee',
        string="Joint Committees",
        help="List all joint committees where the salary rule should be applied",
        context={'active_test': False},
    )

    l10n_be_excluded_joint_committee_ids = fields.Many2many(
        comodel_name='l10n.be.joint.committee',
        relation='salary_rule_joint_committee_rel',
        string="Excluded Joint Committees",
        help="List all joint committees where the salary rule should not be applied",
        context={'active_test': False},
    )

    l10n_be_remuneration_code = fields.Char(string="Remuneration Code", groups='hr_payroll.group_hr_payroll_user')

    l10n_be_remuneration_frequency = fields.Integer(
        string='Remuneration Frequency',
        help="Enter the remuneration frequency to populate the DMFA.",
    )

    l10n_be_is_bonus_remuneration = fields.Boolean(compute='_compute_l10n_be_is_bonus_remuneration')

    l10n_be_fiscal_nature_ids = fields.Many2many(
        'l10n.be.281.mapping', string="Fiscal Nature", compute='_compute_l10n_be_fiscal_nature_ids',
        groups='hr_payroll.group_hr_payroll_user',
    )

    l10n_be_follow_pay_period = fields.Selection(
        selection=lambda self: self._get_l10n_be_follow_pay_period_selection(),
        string="Follow Pay Period", default='never', required=True,
        help="Define when the amounts computed by this rule must be fiscally attached to the pay "
             "period of the payslip rather than to its fiscal period. Example: benefit in kind must "
             "always be attached to the pay period. The delta is what the amount adds to what was "
             "already declared for it, which is nothing outside of a correction.")

    @api.model
    def _get_l10n_be_follow_pay_period_selection(self):
        # Resolved at runtime, so that a stable version may add a policy without the schema change
        # a literal selection would need.
        return [
            ('never', self.env._("Never follow")),
            ('always', self.env._("Always follow")),
            ('positive', self.env._("Follow if delta is positive")),
            ('negative', self.env._("Follow if delta is negative")),
        ]

    @api.depends('l10n_be_remuneration_code')
    def _compute_l10n_be_is_bonus_remuneration(self):
        remuneration_codes = self._get_bonus_remuneration_codes()
        for rule in self:
            rule.l10n_be_is_bonus_remuneration = int(rule.l10n_be_remuneration_code) in remuneration_codes

    @api.constrains('l10n_be_remuneration_frequency')
    def _check_dmfa_frequency_range(self):
        for rule in self:
            if rule.l10n_be_remuneration_frequency < 0 or rule.l10n_be_remuneration_frequency > 99:
                raise ValidationError(self.env._("The DmfA remuneration frequency must be between 0 and 99."))

    @api.depends('code', 'country_code')
    def _compute_l10n_be_fiscal_nature_ids(self):
        today = fields.Date.context_today(self)
        mappings = self.env['l10n.be.281.mapping'].search([
            ('evaluation_type', '=', 'salary_rule'),
            ('date_from', '<=', today),
            '|', ('date_to', '=', False), ('date_to', '>=', today),
        ])
        for rule in self:
            if rule.country_code != 'BE':
                rule.l10n_be_fiscal_nature_ids = False
                continue
            rule.l10n_be_fiscal_nature_ids = mappings.filtered(
                lambda mapping: rule.code in mapping.with_context(active_test=False).salary_rule_ids.mapped('code')
            )

    @api.constrains('l10n_be_remuneration_code')
    def _check_l10n_be_remuneration_code(self):
        for salary_rule in self:
            if salary_rule.l10n_be_remuneration_code and not salary_rule.l10n_be_remuneration_code.isdecimal():
                raise ValidationError(self.env._("Remuneration Code must be an integer for Belgian salary rules."))

    def _satisfy_condition(self, localdict):
        if localdict['payslip'].country_code != 'BE':
            return super()._satisfy_condition(localdict)

        employee_committee = localdict['version'].l10n_be_joint_committee_id
        rule_committees = self.l10n_be_joint_committee_ids
        excluded_rule_committees = self.l10n_be_excluded_joint_committee_ids
        if rule_committees and (not employee_committee or not employee_committee.is_descendant_of(rule_committees)):
            return False

        if excluded_rule_committees and employee_committee and employee_committee.is_descendant_of(excluded_rule_committees):
            return False

        return super()._satisfy_condition(localdict)

    @api.model
    def _get_critical_fields(self):
        return super()._get_critical_fields() + [
            'l10n_be_joint_committee_ids', 'l10n_be_excluded_joint_committee_ids'
        ]

    @api.model
    def _get_bonus_remuneration_codes(self):
        return [2, 23, 45, 62]
