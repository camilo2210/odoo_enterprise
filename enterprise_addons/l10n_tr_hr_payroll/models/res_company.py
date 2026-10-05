# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError


L10N_TR_UNIT_CODE_SELECTION = [
    ("01", "01"),
    ("02", "02"),
    ("03", "03"),
    ("04", "04"),
    ("05", "05"),
    ("06", "06"),
    ("07", "07"),
    ("08", "08"),
    ("09", "09"),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_tr_annual_work_entry_type_id = fields.Many2one(
        'hr.work.entry.type', string="TR Annual Leave Time-off Type",
        domain="[('id', 'in', allowed_work_entry_type_ids)]",
        default=lambda self: self.env.ref('hr_work_entry.tr_work_entry_type_legal_leave', raise_if_not_found=False))
    l10n_tr_sgk_workspace_registration_no = fields.Char(
        string='SGK Workspace Registration Number',
        size=21,
        help="Fill the 7-digit company's SGK-issued workplace registration number.",
    )
    l10n_tr_sgk_intermediary_code = fields.Char(string='Intermediary Code', size=3)
    l10n_tr_tax_reponsible_id = fields.Many2one("hr.employee")
    l10n_tr_old_unit_code = fields.Selection(
        selection=L10N_TR_UNIT_CODE_SELECTION,
        string="Old Unit Code",
        help="Two-digit code identifying the former SGK unit associated with the workplace registration number.",
    )
    l10n_tr_new_unit_code = fields.Selection(
        selection=L10N_TR_UNIT_CODE_SELECTION,
        string="New Unit Code",
        help="Two-digit code identifying the current SGK unit associated with the workplace registration number.",
    )
    l10n_tr_incentive_tier = fields.Selection(
        selection=[('5', '5 points'), ('2', '2 points'), ('0', 'None')],
        string="Incentive Tier",
        help="Deduction points from employer SSI contribution percentage.",
        default='0',
    )

    @api.constrains("l10n_tr_sgk_workspace_registration_no")
    def _check_l10n_tr_sgk_workspace_registration_no(self):
        if any(record.l10n_tr_sgk_workspace_registration_no and len(record.l10n_tr_sgk_workspace_registration_no) < 7 for record in self):
            raise UserError(self.env._("The workplace SGK registration number must be at least 7 digits"))
