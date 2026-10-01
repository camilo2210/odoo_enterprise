# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError
from odoo.tools import convert_file

_logger = logging.getLogger(__name__)


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'
    _description = 'Time Type'

    display_hours = fields.Boolean(
        string="Display Hours",
        help="If checked, the worked hours will be displayed in the payslip worked days lines.")
    round_days_type = fields.Selection(
        [('HALF-UP', 'Closest'),
         ('UP', 'Up'),
         ('DOWN', 'Down')
        ], string="Rounding Method", required=True, default='DOWN',
        help="According to the Duration Rounding, the duration will be rounded to closest, top, or bottom value")
    category_ids = fields.Many2many('hr.salary.rule.category', string="Salary Rule Categories", groups='hr_payroll.group_hr_payroll_user',
        domain="['|', ('country_id', '=', False), ('country_id', '=', country_id)]")
    optional_category_ids = fields.Many2many('hr.salary.rule.category',
        relation='hr_salary_rule_category_options_hr_work_entry_type_rel',
        string="Optional Categories",
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('country_id', '=', country_id)]",
        help="Categories that can be added optionally on time off created by HR user")
    is_extra_hours = fields.Boolean(compute="_compute_is_extra_hours", store=True,
        help="Indicates if the hours are considered as extra time and added as a bonus to the basic salary.")

    modified_by_user = fields.Boolean(readonly=True, copy=False)

    @api.depends('category_ids')
    def _compute_is_extra_hours(self):
        extra_hours_category = self.env.ref('hr_payroll.EXTRA_HOURS', raise_if_not_found=False)
        for work_entry_type in self:
            work_entry_type.is_extra_hours = extra_hours_category in work_entry_type.category_ids if extra_hours_category else False

    def _set_all_external_identifiers_noupdate(self, noupdate):
        self.env['ir.model.data'].sudo().search([
            ('model', '=', "hr.work.entry.type"), ('res_id', 'in', self.ids)
        ]).write({'noupdate': noupdate})
        self.env.flush_all()

    def action_reset_rule(self):
        self.ensure_one()
        self.with_user(SUPERUSER_ID)._update_payroll_related_fields()
        self.with_user(SUPERUSER_ID).write({
            'modified_by_user': False,
            'active': True,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'sticky': False,
                'message': self.env._("Time type successfully reset!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return [(
            'hr_payroll', [
                'data/hr_work_entry_type_data.xml',
            ])]

    def _update_payroll_related_fields(self, country_code=False):
        domain = []
        if not self:
            # That file is flagged `noupdate`: loading it only creates the time types missing from
            # the database, so that the payroll data files below can safely reference the new ones.
            _logger.info("Loading new time types from hr_work_entry/data/hr_work_entry_type_data.xml")
            convert_file(self.env, 'hr_work_entry', 'data/hr_work_entry_type_data.xml', {})
            _logger.info("Loading new time types' Time off data from hr_holidays/data/hr_work_entry_type_data.xml")
            convert_file(self.env, 'hr_holidays', 'data/hr_work_entry_type_data.xml', {})
            domain = [('modified_by_user', '=', False)]
            if country_code:
                domain.append(('country_id.code', 'in', [country_code, False]))

        time_types_to_update = self if self else self.env['hr.work.entry.type'].search(domain)
        time_types_to_update._set_all_external_identifiers_noupdate(False)
        data_to_update = self._get_data_files_to_update()
        for module_name, files_to_update in data_to_update:
            if country_code and not module_name.startswith(f"l10n_{country_code.lower()}"):
                continue
            for file_to_update in files_to_update:
                _logger.info("Updating %s/%s", module_name, file_to_update)
                convert_file(self.env, module_name, file_to_update, {})

    @api.ondelete(at_uninstall=False)
    def _unlink_except_work_entry_type(self):
        if self and self.env.uid != SUPERUSER_ID:
            raise UserError(_("You cannot delete time type(s). Instead archive it."))

    @api.model
    def _get_critical_fields(self):
        return ['amount_rate', 'display_hours', 'round_days_type', 'category_ids', 'optional_category_ids', 'is_extra_hours']

    def write(self, vals):
        types_created_by_system = self.filtered(
            lambda r: r.sudo().create_uid.id == SUPERUSER_ID
        )
        if (
            self.env.uid != SUPERUSER_ID
            and types_created_by_system
            and any(f in vals for f in self._get_critical_fields())
        ):
            types_created_by_system._set_all_external_identifiers_noupdate(True)
            vals["modified_by_user"] = True
        result = super().write(vals)
        return result
