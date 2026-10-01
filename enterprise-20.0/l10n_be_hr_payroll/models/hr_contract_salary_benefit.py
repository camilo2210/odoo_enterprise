from odoo import fields, models


class HrContractSalaryBenefit(models.Model):
    _inherit = 'hr.contract.salary.benefit'

    l10n_be_joint_committee_ids = fields.Many2many(
        comodel_name='l10n.be.joint.committee',
        string="Joint Committees",
        help="List all joint committees where the benefit rule should be applied",
        context={'active_test': False},
    )
    l10n_be_excluded_joint_committee_ids = fields.Many2many(
        comodel_name='l10n.be.joint.committee',
        relation='hr_contract_salary_benefit_excluded_joint_committee_rel',
        string="Excluded Joint Committees",
        help="List all joint committees where the benefit rule should not be applied",
        context={'active_test': False},
    )
