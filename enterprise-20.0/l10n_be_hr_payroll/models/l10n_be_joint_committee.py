# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class L10nBeJointCommittee(models.Model):
    _name = 'l10n.be.joint.committee'
    _description = 'BE: Joint Committee'
    _parent_store = True
    _rec_names_search = ('name', 'egov3_code')

    name = fields.Char(required=True, translate=True)
    egov3_code = fields.Char(string="Code")
    version_ids = fields.One2many('hr.version', 'l10n_be_joint_committee_id')
    parent_id = fields.Many2one('l10n.be.joint.committee', string='Parent Committee', index=True)
    parent_path = fields.Char(index=True)
    selectable = fields.Boolean(string="Selectable", help="Allow to select it on employee form", default=True)
    active = fields.Boolean(string="Active", default=True)

    @api.constrains('egov3_code', 'selectable')
    def _check_egov3_code_format(self):
        pattern = re.compile(r'^\d+(?:\.\d+)*$')
        for record in self:
            if record.selectable and record.egov3_code and not pattern.match(record.egov3_code):
                raise ValidationError(self.env._(
                    "The eGov3 code must contain only digits and dots. (e.g. 305, 305.01, 305.02.01)"
                ))

    @api.depends('egov3_code', 'name')
    @api.depends_context('formatted_display_name')
    def _compute_display_name(self):
        for category in self:
            parent_name = f"{category.parent_id.name} - " if category.parent_id else ''
            if self.env.context.get('formatted_display_name'):
                category.display_name = f"{category.egov3_code}\t--{parent_name}{category.name}--"
            else:
                category.display_name = f"{category.egov3_code}"

    def is_descendant_of(self, others):
        """
        Returns True if `self` is a descendant of any committee in `others`.
        """
        self.ensure_one()
        return any(self.parent_path.startswith(other.parent_path) for other in others)

    def write(self, vals):
        res = super().write(vals)
        if vals.get('active', False):
            self._activate_related_payroll_records()
        if not vals.get('active', True):
            self._deactivate_related_payroll_records()
        return res

    def _activate_related_payroll_records(self):
        """
        Activates related payroll records when a joint committee is activated.
        """
        joint_committee_domain = [
            ("l10n_be_joint_committee_ids", "in", self.ids + [False]),
            ("country_id", "=", self.env.ref('base.be').id),
            ("active", "=", False),
        ]
        models_to_activate = (
            "hr.payroll.structure",
            "hr.salary.rule",
            "hr.payroll.warning",
            "hr.salary.rule.category",
        )
        for model_name in models_to_activate:
            candidates = self.env[model_name].with_context(active_test=False).search(
                joint_committee_domain,
            )
            if model_name == "hr.payroll.warning":
                candidates -= self.env.ref('l10n_be_hr_payroll.hr_payroll_warning_invalid_work_address', raise_if_not_found=False)
            if model_name != "hr.salary.rule.category":
                candidates = candidates.filtered(
                    lambda candidate: ((candidate.l10n_be_joint_committee_ids & self) if candidate.l10n_be_joint_committee_ids else self)
                    - candidate.l10n_be_excluded_joint_committee_ids,
                )
            if model_name == "hr.salary.rule":
                benefits = self.env["hr.contract.salary.benefit"].with_context(active_test=False).search([('salary_rule_ids', 'in', candidates.ids)])
                rules_related_to_archived_benefits_only = (benefits - benefits.filtered(lambda benefit: benefit.active)).salary_rule_ids
                candidates = candidates - rules_related_to_archived_benefits_only
            candidates.active = True

    def _deactivate_related_payroll_records(self):
        """
        Deactivates related payroll records when a joint committee is deactivated.
        """
        versions_using_committee = self.env["hr.version"].search([("l10n_be_joint_committee_id", "in", self.ids)])
        if versions_using_committee:
            raise UserError(
                self.env._("The following joint committees are used in payroll versions and cannot be deactivated: %s")
                % ", ".join(versions_using_committee.mapped("l10n_be_joint_committee_id.egov3_code"))
            )

        joint_committee_domain = [
            ("active", "=", True),
            ("l10n_be_joint_committee_ids", "in", self.ids),
            ("country_id", "=", self.env.ref('base.be').id),
        ]
        models_to_deactivate = (
            "hr.payroll.structure",
            "hr.salary.rule",
            "hr.payroll.warning",
            "hr.salary.rule.category",
        )
        for model_name in models_to_deactivate:
            candidates = self.env[model_name].with_context(active_test=False).search(
                joint_committee_domain,
            )
            if model_name != "hr.salary.rule.category":
                candidates = candidates.filtered(
                    lambda candidate: (candidate.l10n_be_joint_committee_ids & self) - candidate.l10n_be_excluded_joint_committee_ids,
                )
            records_to_deactivate = candidates.filtered(lambda r: not any(joint_committee.active for joint_committee in r.l10n_be_joint_committee_ids))
            records_to_deactivate.active = False
