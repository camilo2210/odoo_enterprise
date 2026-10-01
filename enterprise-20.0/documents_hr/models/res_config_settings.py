# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    documents_employee_folder_id = fields.Many2one(
        'documents.document', check_company=True,
        related='company_id.documents_employee_folder_id', readonly=False)
    employee_subfolders = fields.Char(
        "Employees Subfolder", related='company_id.employee_subfolders', readonly=False,
        help='Comma separated string of folder names that need to be created under each employee folder.')
    documents_hr_contracts_tags = fields.Many2many(
        'documents.tag', 'documents_hr_contracts_tags_table', related='company_id.documents_hr_contracts_tags',
        readonly=False, string="Contracts")
    documents_hr_group_id = fields.Many2one(
        'res.group.functional', related='company_id.documents_hr_group_id', readonly=False)
