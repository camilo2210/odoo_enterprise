from odoo import fields, models


class HrSalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'

    l10n_be_joint_committee_ids = fields.Many2many(
        comodel_name='l10n.be.joint.committee',
        string="Joint Committees",
        help="List all joint committees where the salary category should be applied",
        context={'active_test': False},
    )

    def _get_seized_categories(self):
        res = super()._get_seized_categories()
        l10n_be_seized = self.env.ref('l10n_be_hr_payroll.SEIZED_AMOUNT', raise_if_not_found=False)
        if l10n_be_seized:
            res |= l10n_be_seized
        return res
