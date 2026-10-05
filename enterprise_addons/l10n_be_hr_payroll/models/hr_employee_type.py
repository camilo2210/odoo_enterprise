from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployeeType(models.Model):
    _inherit = 'hr.employee.type'
    _description = 'Employee Type'

    l10n_be_worker_code_ids = fields.Many2many(
        'l10n.be.worker.code',
        relation='l10n_be_worker_code_employee_type_rel', column1='employee_type_id', column2='worker_code_id',
        string="Sub-types")
    l10n_be_dimona_category = fields.Selection(
        selection=lambda self: self.env['hr.version']._get_l10n_be_dimona_category_selection(),
        string='DIMONA Category',
        help='Used as the worker type for DIMONA declaration to the ONSS',
    )
    l10n_be_joint_committee_id = fields.Many2one('l10n.be.joint.committee', "Joint Committee")
    company_country_code = fields.Char(related='company_id.country_code', string="Company Country Code")

    @api.constrains('country_id', 'company_id')
    def _check_country_company_compatibility(self):
        for employee_type in self:
            if employee_type.country_id and employee_type.company_id and employee_type.country_id != employee_type.company_id.country_id:
                raise ValidationError(self.env._(
                    "The country of the related company is not compatible with the country of this employee type."
                ))
