from odoo import fields, models


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    l10n_be_joint_committee_ids = fields.Many2many(
        comodel_name='l10n.be.joint.committee',
        string="Joint Committees",
        help="List all joint committees where the structure should be applied",
        context={'active_test': False},
    )
    l10n_be_excluded_joint_committee_ids = fields.Many2many(
        comodel_name='l10n.be.joint.committee',
        relation='hr_payroll_structure_excluded_joint_committee_rel',
        string="Excluded Joint Committees",
        help="List all joint committees where the structure should not be applied",
        context={'active_test': False},
    )

    def get_joint_committee_rules(self, joint_committee_id):
        joint_committee = self.env['l10n.be.joint.committee'].browse(joint_committee_id)
        rules = self.rule_ids.filtered(
            lambda rule: not rule.l10n_be_joint_committee_ids
            or joint_committee and joint_committee.is_descendant_of(rule.l10n_be_joint_committee_ids))

        return rules.ids
