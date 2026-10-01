# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class L10nBeWorkerCode(models.Model):
    _name = 'l10n.be.worker.code'
    _description = 'BE: Worker Code'
    _rec_names_search = ('dmfa_code', 'egov3_code', 'name')

    name = fields.Char(required=True, translate=True)
    description = fields.Char(translate=True)
    egov3_code = fields.Char(required=True)
    dmfa_code = fields.Char(required=True)
    employee_type_ids = fields.Many2many(
        'hr.employee.type',
        relation='l10n_be_worker_code_employee_type_rel', column1='worker_code_id', column2='employee_type_id',
        string="Employee Types",
        help="Employee types this worker code applies to. Leave empty if it applies to any employee type.")
    joint_committee_ids = fields.Many2many('l10n.be.joint.committee', string="Joint Committees")

    @api.depends('dmfa_code', 'name')
    @api.depends_context('formatted_display_name')
    def _compute_display_name(self):
        for category in self:
            if self.env.context.get('formatted_display_name'):
                category.display_name = f"{category.name}\t--{category.dmfa_code}--"
            else:
                category.display_name = category.name or category.dmfa_code
