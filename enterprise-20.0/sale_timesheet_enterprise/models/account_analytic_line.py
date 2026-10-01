# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools import SQL
from odoo.addons.sale_timesheet_enterprise.models.sale_order_line import DEFAULT_INVOICED_TIMESHEET


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    is_billable = fields.Boolean(
        compute="_compute_is_billable",
        inverse="_inverse_is_billable",
    )
    is_billable_select = fields.Selection(
        [('true', 'Billable'), ('false', 'Non-billable')],
        compute_sudo=False,
        compute="_compute_is_billable",
        compute_sql="_sql_compute_is_billable",
    )

    has_available_so = fields.Boolean(
        compute='_compute_has_available_so',
        groups="sales_team.group_sale_salesman",
        help="Simulates if checking 'is_billable' will actually attach an SO line."
    )

    @api.depends('validated')
    def _compute_so_line(self):
        updatable_timesheets = self.filtered(lambda t: t._is_updatable_timesheet())
        super(AccountAnalyticLine, updatable_timesheets)._compute_so_line()

    @api.depends('so_line')
    def _compute_is_billable(self):
        for record in self:
            record.is_billable = bool(record.so_line)
            record.is_billable_select = 'true' if bool(record.so_line) else 'false'

    def _inverse_is_billable(self):
        for record in self:
            if not record.is_billable:
                record.so_line = False
            else:
                record._compute_so_line()

    def _sql_compute_is_billable(self, table):
        return SQL("CASE WHEN %s IS NOT NULL THEN 'true' ELSE 'false' END", table._sudo().so_line)

    @api.depends('so_line', 'task_id.sale_line_id', 'project_id.sale_line_id', 'employee_id', 'project_id.allow_billable')
    def _compute_has_available_so(self):
        for record in self:
            if record.so_line:
                record.has_available_so = True
                continue
            record.has_available_so = bool(record._timesheet_determine_sale_line())

    @api.model
    def grid_update_cell(self, domain, measure_field_name, value):
        return super().grid_update_cell(
            Domain.AND([domain, [('reinvoice_move_id', '=', False), ('project_id', '!=', False)]]),
            measure_field_name,
            value,
        )

    def _is_updatable_timesheet(self):
        return super()._is_updatable_timesheet() and not self.validated

    def _timesheet_get_portal_domain(self):
        domain = super()._timesheet_get_portal_domain()
        param_invoiced_timesheet = self.env['ir.config_parameter'].sudo().get_str('sale.invoiced_timesheet') or DEFAULT_INVOICED_TIMESHEET
        if param_invoiced_timesheet == 'approved':
            domain = Domain.AND([domain, [('validated', '=', True)]])
        return domain

    def _compute_can_validate(self):
        # Prevent `user_can_validate` from being true if the line is validated and the SO aswell
        billed_lines = self.filtered(lambda l: l.validated and not l._is_not_billed())
        for line in billed_lines:
            line.user_can_validate = False
        self -= billed_lines
        return super()._compute_can_validate()

    def action_invalidate_timesheet(self):
        invoice_validated_timesheets = self.filtered(lambda l: not l._is_not_billed())
        self -= invoice_validated_timesheets
        # Errors are handled in the parent if there are no lines left
        return super().action_invalidate_timesheet()

    @api.model
    def get_kpi_data(self, date_start, date_stop):
        if not self.env.user.has_group("hr_timesheet.group_hr_timesheet_user"):
            return {}

        date_start = fields.Date.from_string(date_start)
        date_stop = fields.Date.from_string(date_stop)

        timesheets = self.search([
            ('user_id', '=', self.env.user.id),
            ('project_id', '!=', False),
            ('date', '>=', date_start),
            ('date', '<=', date_stop),
        ])
        billable_timesheets = timesheets.filtered_domain([('billable_type', '!=', '09_non_billable')])

        worked_time = sum(timesheets.mapped('unit_amount'))
        billable_time = sum(billable_timesheets.mapped('unit_amount'))
        uom = self.env.user.company_id.timesheet_encode_uom_id.name
        data = {
            'worked_time': worked_time,
            'billable_time': billable_time,
            'uom': uom,
        }

        if not (self.env.company.timesheet_show_rates and self.env.user.employee_id.billable_time_target > 0):
            return data

        billable_time_target = self.env.user.employee_id.billable_time_target
        billing_rate = billable_time / billable_time_target
        return {
            **data,
            'billable_time_target': billable_time_target,
            'billing_rate': billing_rate,
        }

    @api.model
    def _get_aw_timesheet_fields_specification(self):
        res = {
            **super()._get_aw_timesheet_fields_specification(),
            'allow_billable': {},
            'so_line': {
                'fields': {'display_name': {}},
            },
        }

        if self.env.user.has_group('sales_team.group_sale_salesman'):
            res['is_billable'] = {}
            res['has_available_so'] = {}

        return res

    @api.model
    def _get_assistant_odoo_models(self):
        return {
            **super()._get_assistant_odoo_models(),
            'sale.order': {
                'label': self.env._('Configuring Sales Order'),
                'target': {
                    'type': 'field',
                    'target_model': 'project.project',
                    'field': 'project_id',
                },
            },
        }

    def action_open_account_analytic_line_origine(self):
        self.ensure_one()
        if self.task_id:
            return {
                'res_model': self.task_id._name,
                'type': 'ir.actions.act_window',
                'views': [[False, "form"]],
                'res_id': self.task_id.id,
            }
        elif self.project_id:
            return {
                'res_model': self.project_id._name,
                'type': 'ir.actions.act_window',
                'views': [[False, "form"]],
                'res_id': self.project_id.id,
            }
        return super().action_open_account_analytic_line_origine()
