from odoo import fields, models


class HrSalaryAttachment(models.Model):
    _inherit = 'hr.salary.attachment'

    l10n_be_dependent_children_attachment = fields.Integer(related='employee_id.version_id.l10n_be_dependent_children_attachment', readonly=False,
        help="The portion of income subject to an attachment of earnings order may be reduced according to the number of dependent children")
