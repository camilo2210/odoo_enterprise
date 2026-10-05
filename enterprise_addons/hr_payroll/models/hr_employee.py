# Part of Odoo. See LICENSE file for full copyright and licensing details.
from __future__ import annotations

import typing

from odoo import api, fields, models

if typing.TYPE_CHECKING:
    from odoo.api import ValuesType
    from odoo.models import BaseModel
    from odoo.addons.mail.tools.discuss import Store


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    _description = 'Employee'

    currency_id = fields.Many2one(
        "res.currency",
        string='Currency',
        related='company_id.currency_id')
    slip_ids = fields.One2many('hr.payslip', 'employee_id', string='Payslips', readonly=True, groups="hr_payroll.group_hr_payroll_user")
    payslip_count = fields.Integer(compute='_compute_payslip_count', string='Payslip Count', groups="hr_payroll.group_hr_payroll_user")
    registration_number = fields.Char('Employee Reference', groups="hr.group_hr_user", copy=False, tracking=True)
    salary_attachment_ids = fields.One2many(
        'hr.salary.attachment',
        'employee_id',
        string='Payslip Adjustments',
        groups="hr_payroll.group_hr_payroll_user")
    salary_attachment_count = fields.Integer(
        compute='_compute_salary_attachment_count', string="Payslip Adjustment Count",
        groups="hr_payroll.group_hr_payroll_user")
    mobile_invoice = fields.Binary(string="Mobile Subscription Invoice", groups="hr.group_hr_manager")
    sim_card = fields.Binary(string="SIM Card Copy", groups="hr.group_hr_manager")
    internet_invoice = fields.Binary(string="Internet Subscription Invoice", groups="hr.group_hr_manager")
    sim_card_name = fields.Char(groups="hr.group_hr_manager")
    internet_invoice_name = fields.Char(groups="hr.group_hr_manager")
    schedule_pay = fields.Selection(readonly=False, related="version_id.schedule_pay", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    fixed_term = fields.Boolean(readonly=False, related="version_id.fixed_term", inherited=True)
    trial_date_end = fields.Date(readonly=False, related="version_id.trial_date_end", inherited=True)
    wage = fields.Monetary(readonly=False, related="version_id.wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    wage_type = fields.Selection(readonly=False, related="version_id.wage_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    hourly_wage = fields.Float(readonly=False, related="version_id.hourly_wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    payslips_count = fields.Integer(related="version_id.payslips_count", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    work_time_rate = fields.Float(related="version_id.work_time_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    disabled = fields.Boolean(readonly=False, related="version_id.disabled", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    date_start = fields.Date(related="version_id.date_start", inherited=True)
    date_end = fields.Date(related="version_id.date_end", inherited=True)
    is_current = fields.Boolean(related="version_id.is_current", inherited=True)
    is_past = fields.Boolean(related="version_id.is_past", inherited=True)
    is_future = fields.Boolean(related="version_id.is_future", inherited=True)
    is_in_contract = fields.Boolean(related="version_id.is_in_contract", inherited=True)
    structure_type_id = fields.Many2one(related="version_id.structure_type_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    employee_type_id = fields.Many2one(related="version_id.employee_type_id", inherited=True, groups="hr.group_hr_manager,hr_payroll.group_hr_payroll_user")
    structure_id = fields.Many2one(related="version_id.structure_id", inherited=True, groups="hr.group_hr_user")
    payroll_properties = fields.Properties(readonly=False, related="version_id.payroll_properties", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    monthly_running_attachments = fields.Monetary(
        compute='_compute_monthly_running_attachments',
        groups="hr_payroll.group_hr_payroll_user")
    issues = fields.Json(related="version_id.issues", groups="hr.group_hr_user,hr_payroll.group_hr_payroll_user")
    review_state = fields.Selection([
        ('1_reviewed', 'Reviewed'),
        ('2_to_review', 'To Review'),
        ('3_anomaly', 'Anomaly'),
    ], string='Review State', default=lambda self: self._default_review_state(), required=True,
        help='State of the review for tracked field changes with tracking < 10', groups="hr.group_hr_user")
    date_to_review = fields.Datetime('Date To Review', help='Date when tracked fields were changed and need review', groups="hr.group_hr_user")
    external_code = fields.Char(groups="hr_payroll.group_hr_payroll_user")
    contract_template_id = fields.Many2one(groups="hr.group_hr_user,hr_payroll.group_hr_payroll_user")

    # departure
    departure_id = fields.Many2one(groups="hr_payroll.group_hr_payroll_user")
    departure_reason_id = fields.Many2one(groups="hr_payroll.group_hr_payroll_user")
    departure_description = fields.Html(groups="hr_payroll.group_hr_payroll_user")
    dismissal_date = fields.Date(groups="hr_payroll.group_hr_payroll_user")
    departure_action_date = fields.Date(groups="hr_payroll.group_hr_payroll_user")
    departure_apply_immediately = fields.Boolean(groups="hr_payroll.group_hr_payroll_user")
    departure_apply_date = fields.Date(groups="hr_payroll.group_hr_payroll_user")
    final_yearly_costs = fields.Monetary(readonly=False, related="version_id.final_yearly_costs", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    off_cycle_invisible = fields.Boolean(compute="_compute_off_cycle_invisible", groups="hr_payroll.group_hr_payroll_user")

    _unique_registration_number = models.Constraint(
        'UNIQUE(registration_number, company_id)',
        "No duplication of registration numbers is allowed",
    )

    def _default_review_state(self):
        if not self.env.su and not self.env.user.has_group('hr_payroll.group_hr_payroll_officer'):
            return '2_to_review'
        return '1_reviewed'

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group('hr_payroll.group_hr_payroll_officer'):
            now = fields.Datetime.now()
            for vals in vals_list:
                vals.update({
                    'review_state': '2_to_review',
                    'date_to_review': now,
                })
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            payroll_props = vals.get('payroll_properties', [])
            if payroll_props and not record.payroll_properties:
                record.payroll_properties = payroll_props
        return records

    def write(self, vals):
        if 'review_state' in vals and vals['review_state'] != '2_to_review':
            vals['date_to_review'] = False

        if not self.env.user.has_group('hr_payroll.group_hr_payroll_officer'):

            tracked_field_names = [
                field_name for field_name, field in self.env['hr.version']._fields.items()
                if hasattr(field, 'tracking') and field.tracking and field.tracking < 10
            ]

            if any(field_name in vals for field_name in tracked_field_names):
                vals['review_state'] = '2_to_review'
                if not vals.get('date_to_review') and not any(emp.date_to_review for emp in self):
                    vals['date_to_review'] = fields.Datetime.now()

        return super().write(vals)

    def _compute_payslip_count(self):
        for employee in self:
            employee.payslip_count = len(employee.slip_ids)

    def _compute_salary_attachment_count(self):
        for employee in self:
            employee.salary_attachment_count = len(employee.salary_attachment_ids)

    def _compute_monthly_running_attachments(self):
        for employee in self:
            running_attachment_ids = employee.salary_attachment_ids.filtered(lambda a: a.state == '1_open')
            employee.monthly_running_attachments = sum(running_attachment_ids.mapped("amount"))

    def action_open_payslips(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr_payroll.action_view_hr_payslip_month_form")
        list_view_id = self.env.ref('hr_payroll.view_hr_payslip_list_employee_payslips').id
        action.update({
            'domain': [('employee_id', '=', self.id)],
            'views': [(list_view_id, 'list'), (False, 'form'), (False, 'activity')],
            'context': {
                'default_employee_id': self.id,
                'search_default_group_by_date_from': 1,
            },
        })
        return action

    def action_open_salary_attachments(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr_payroll.hr_salary_attachment_action")
        action.update({'domain': [('employee_id', '=', self.id)],
                       'context': {'default_employee_id': self.id}})
        return action

    def _increase_employee_salary(self):
        action = self.env["ir.actions.actions"]._for_xml_id("hr_payroll.action_hr_payroll_salary_increase")
        action['context'] = {'default_employee_ids': self.ids}
        return action

    def action_archive(self):
        attachments_to_close = self.sudo().salary_attachment_ids.filtered_domain([
            ('state', '=', '1_open')
        ])
        attachments_to_close.action_close()
        for attachment in attachments_to_close:
            attachment.message_post(
                body=self.env._("The Salary Attachment has been automatically closed because %s has been archived.")
                % attachment.employee_id.name
            )

        return super().action_archive()

    @api.model
    def _get_account_holder_employees_data(self):
        # as account_type isn't stored we can not use a domain to retrieve the employees
        # bypass orm for performance, we only care about the employee id anyway

        # return nothing if user has no right to either employee or bank partner
        if (not self.browse().has_access('read') or
                not self.env['res.partner.bank'].has_access('read')):
            return []

        self.env.cr.execute('''
            SELECT emp.id,
                   acc.account_number,
                   acc.allow_out_payment
              FROM hr_employee emp
         LEFT JOIN employee_bank_account_rel rel
                ON rel.employee_id=emp.id
         LEFT JOIN res_partner_bank acc
                ON acc.id=rel.bank_account_id
             WHERE emp.company_id IN %s
               AND emp.active = TRUE
        ''', (tuple(self.env.companies.ids),))

        return self.env.cr.dictfetchall()

    @api.model
    def _get_untrusted_bank_account_ids(self):
        """Return a list of bank account IDs linked to employees that are not marked for out payment."""
        if (not self.browse().has_access('read') or
                not self.env['res.partner.bank'].has_access('read')):
            return []

        self.env.cr.execute('''
            SELECT acc.id
            FROM res_partner_bank acc
            JOIN employee_bank_account_rel rel
                ON rel.bank_account_id = acc.id
            JOIN hr_employee emp
                ON emp.id = rel.employee_id
            WHERE acc.allow_out_payment = FALSE
            AND emp.company_id IN %s
            AND emp.active = TRUE
        ''', (tuple(self.env.companies.ids),))
        # Return ids of untrusted bank accounts.
        return [row[0] for row in self.env.cr.fetchall()]

    def action_add_payslip_to_payrun(self, payrun_id):
        self.ensure_one()
        payrun = self.env['hr.payslip.run'].browse(payrun_id)
        if not payrun or not payrun.exists():
            return {'type': 'ir.actions.act_window_close'}

        payslip_vals = {
            'employee_id': self.id,
            'company_id': self.company_id.id,
            'payslip_run_id': payrun_id,
            'date_from': payrun.date_start,
            'date_to': payrun.date_end,
            'struct_id': self.structure_id.id,
        }
        payslip = self.env['hr.payslip'].create(payslip_vals)
        payslip._compute_name()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _recompute_worked_days_lines(self):
        if not self:
            return
        draft_payslips = self.env["hr.payslip"].search([
            ("employee_id", "in", self.ids),
            ("state", "=", "draft")])
        if draft_payslips:
            draft_payslips._compute_worked_days_line_ids()

    def _store_avatar_card_fields(self, res: Store.FieldList):
        super()._store_avatar_card_fields(res)
        if self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            res.extend(["wage", "hourly_wage", "wage_type", "first_contract_date"])
            res.one("employee_type_id", ["name"])
            res.one("currency_id", ["symbol", "position", "decimal_places"])

    def _track_log(
        self,
        track_init_values: dict[int, ValuesType],
        trackings: dict[int, tuple[set[str], list[ValuesType]]],
        track_records: BaseModel | None = None
    ):
        """Split payroll-sensitive tracking values into a dedicated message subtype.
        Tracking values linked to payroll-restricted fields are posted separately
        so they can be filtered from the employee chatter for users without
        payroll access.
        """
        # Collect tracked field ids from tracking values
        field_ids = {
            tracking.get('field_id')
            for _record_id, (_changes, tracking_values) in trackings.items()
            for tracking in tracking_values
            if tracking.get('field_id')
        }
        payroll_field_ids = set()
        if field_ids:
            field_records = self.env['ir.model.fields'].sudo().browse(field_ids)
            # Keep only payroll-restricted fields
            payroll_field_ids = {
                field.id
                for field in field_records
                if (model_field := self.env[field.model]._fields.get(field.name))
                and 'hr_payroll.group_hr_payroll_user' in (model_field.groups or '')
            }

        payroll_trackings = {}
        normal_trackings = {}

        for record_id, (_changes, tracking_values) in trackings.items():
            # Split payroll and non-payroll tracking values
            payroll_vals = [tracking for tracking in tracking_values if tracking.get('field_id') in payroll_field_ids]
            normal_vals = [tracking for tracking in tracking_values if tracking.get('field_id') not in payroll_field_ids]

            if normal_vals:
                normal_trackings[record_id] = ({val['field_name'] for val in normal_vals}, normal_vals)
            if payroll_vals:
                payroll_trackings[record_id] = ({val['field_name'] for val in payroll_vals}, payroll_vals)

        # Post regular tracking message
        if normal_trackings:
            super()._track_log(track_init_values, normal_trackings, track_records=track_records)

        # Post payroll tracking message
        if payroll_trackings:
            payroll_init_values = {
                record_id: {
                    col: track_init_values[record_id][col]
                    for col in payroll_changes
                    if col in track_init_values.get(record_id, {})
                }
                for record_id, (payroll_changes, payroll_vals) in payroll_trackings.items()
            }
            super()._track_log(payroll_init_values, payroll_trackings, track_records=track_records)

    def _track_log_get_default_subtype(self, track_init_values):
        self.ensure_one()
        for fname in track_init_values:
            model_field = self._fields.get(fname)
            if (
                model_field
                and 'hr_payroll.group_hr_payroll_user' in (model_field.groups or '')
            ):
                return self.env.ref('hr_payroll.mt_hr_payroll_sensitive')
        return super()._track_log_get_default_subtype(track_init_values)

    def _compute_off_cycle_invisible(self):
        for employee in self:
            payrun_id = employee.env.context.get('payrun_id')
            payrun = employee.env['hr.payslip.run'].browse(payrun_id)
            employee.off_cycle_invisible = payrun and payrun.state not in ['00_draft', '01_ready']

    def get_benefit_fields_value(self, version_id):
        if not self.env.user.has_groups('hr_payroll.group_hr_payroll_user'):
            return []
        self.ensure_one()
        version = self.version_id
        if version_id:
            version = self.env['hr.version'].browse(version_id)
            if version.employee_id != self:
                raise ValueError(self.env._("The corresponding version does not belong to employee %(name)s.", name=self.name))
        return version.get_benefit_fields_value()
