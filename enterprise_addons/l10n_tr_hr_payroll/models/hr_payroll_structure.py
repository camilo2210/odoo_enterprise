# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    l10n_tr_remote_work_entry_type_ids = fields.Many2many(string="Remote Work Entry Types", comodel_name='hr.work.entry.type', relation='hr_payroll_structure_hr_work_entry_type_remote_rel')
