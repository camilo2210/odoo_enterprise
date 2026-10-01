from odoo import api, fields, models


class L10nBeSalaryScale(models.Model):
    _name = 'l10n_be.salary.scale'
    _description = 'Salary Scale'

    name = fields.Char(required=True, translate=True)
    l10n_be_joint_committee = fields.Many2one('l10n.be.joint.committee', string="Related Joint Committee", required=True)
    code = fields.Char(string="Code", required=True)
    description = fields.Char()
    dmfa_code = fields.Char(string="DMFA Code")
    egov3_code = fields.Char(string="eGov3 Code")
    employer_category_id = fields.Many2one(
        'l10n.be.employer.category', string="Employer Category",
        domain="[('allowed_joint_committee_ids', 'any', [('id', '=', l10n_be_joint_committee)])]")

    @api.depends('code', 'dmfa_code')
    @api.depends_context('formatted_display_name')
    def _compute_display_name(self):
        for salary_scale in self:
            if self.env.context.get('formatted_display_name'):
                salary_scale.display_name = f"{salary_scale.name}\t--{salary_scale.description}--"
            elif salary_scale.dmfa_code:
                salary_scale.display_name = f'[{salary_scale.dmfa_code}] {salary_scale.name}'
            else:
                salary_scale.display_name = salary_scale.name
