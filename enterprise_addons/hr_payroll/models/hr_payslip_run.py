# Part of Odoo. See LICENSE file for full copyright and licensing details.
from ast import literal_eval
from datetime import date, datetime, time, UTC

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, Command
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.tools.date_utils import get_month

STATUS_COLOR = {
    '00_draft': 0,
    '01_ready': 4,  # info light blue
    '02_close': 10,  # success green
    '03_paid': 5,  # primary purple
    '04_cancel': 0,  # default grey
    False: 0,  # default grey -- for studio
}


class HrPayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Pay Run'
    _explanation = "Represents a batch of payslips for a specific period, allowing bulk generation, validation, and management of employee salaries."
    _order = 'date_end desc'

    active = fields.Boolean(default=True)
    name = fields.Char(compute='_compute_name', readonly=False, store=True, required=True, precompute=True)
    slip_ids = fields.One2many('hr.payslip', 'payslip_run_id', string='Payslips')
    state = fields.Selection([
            ('00_draft', 'Draft'),
            ('01_ready', 'Ready'),
            ('02_close', 'Done'),
            ('03_paid', 'Paid'),
            ('04_cancel', 'Cancelled'),
        ],
        string='Status', index=True, readonly=True, copy=False,
        default='00_draft', tracking=True, required=True,
        compute='_compute_state', store=True)
    color = fields.Integer(compute='_compute_color', export_string_translation=False)
    date_start = fields.Date(
        string='From', readonly=False, required=True,
        compute="_compute_date_start", store=True, precompute=True,
        default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_end = fields.Date(
        string='To', readonly=False, required=True,
        compute="_compute_date_end", store=True, precompute=True,
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    structure_id = fields.Many2one(
        'hr.payroll.structure', string='Pay Structure', readonly=False, required=True, index=True,
        default=lambda self: self.env['hr.payroll.structure'].search([('country_id', '=', self.env.company.country_id.id), ('use_worked_day_lines', '=', True)], limit=1))
    use_worked_day_lines = fields.Boolean(related='structure_id.use_worked_day_lines')
    payslip_count = fields.Integer(compute='_compute_payslip_count', store=True)
    payslips_with_warnings = fields.Integer(compute='_compute_payslips_with_warnings_and_errors')
    payslips_with_errors = fields.Integer(compute='_compute_payslips_with_warnings_and_errors')
    empty_payslips = fields.Integer(compute='_compute_empty_payslips')
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    country_id = fields.Many2one(
        'res.country', string='Country',
        related='company_id.country_id', readonly=True, search='_search_country_id'
    )
    country_code = fields.Char(related='country_id.code', depends=['country_id'], readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    payment_report = fields.Binary(
        string='Payment Report',
        help="Export .csv file related to this pay run",
        readonly=True)
    payment_report_filename = fields.Char(readonly=True)
    payment_report_format = fields.Char(readonly=True)
    payment_report_date = fields.Date(readonly=True)
    total_employer_cost = fields.Monetary(compute='_compute_total_employer_cost', string='Total Employer Cost')
    gross_sum = fields.Monetary(compute="_compute_gross_net_sum", store=True, readonly=True, copy=False)
    net_sum = fields.Monetary(compute="_compute_gross_net_sum", store=True, readonly=True, copy=False)

    version_ids = fields.Many2many('hr.version', relation="hr_payslip_run_hr_version_rel", compute='_compute_version_ids', store=True)
    employee_count = fields.Integer(compute='_compute_employee_count', store=True)

    employee_type_ids = fields.Many2many('hr.employee.type', string='Employee Types')
    structure_domain = fields.Char(compute='_compute_structure_domain')
    payslip_generate_and_send_trigger = fields.Selection(related="company_id.payslip_generate_and_send_trigger")

    _check_dates = models.Constraint('CHECK(date_start <= date_end)', 'The start date must be before or equal to the end date.')

    def _get_name_for_period(self, vals=None, cache=None):

        def normalize_date(val):
            if isinstance(val, date):
                return val
            elif isinstance(val, datetime):
                return val.date()
            elif isinstance(val, str):
                return date.fromisoformat(val)
            return None

        if vals is None:
            vals = {}
        if cache is None:
            cache = {}
        if not vals.get("date_start") or not vals.get("date_end"):
            raise UserError(self.env._("You must set a start and end date for the Pay Run"))
        date_start = normalize_date(vals["date_start"])
        date_end = normalize_date(vals["date_end"])
        structure_id = vals.get("structure_id")
        name = ""
        if not date_start or not date_end:
            return name
        format_date_cached = self.env["hr.payslip"]._format_date_cached
        if date_end.year == date_start.year:
            if date_end.month - date_start.month == 11:
                name += format_date_cached(cache, date_start, date_format="Y")
            elif date_end.month == date_start.month:
                if (date_start, date_end) == get_month(date_start):
                    name += format_date_cached(cache, date_start, date_format="MMM Y")
                elif date_start.day == date_end.day:
                    name += format_date_cached(cache, date_start, date_format="d MMM Y")
                else:
                    name += format_date_cached(cache, date_start, date_format="d MMM Y") + " - " + format_date_cached(cache, date_end, date_format="d MMM Y")
            else:
                name += format_date_cached(cache, date_start, date_format="MMM Y") + " - " + format_date_cached(cache, date_end, date_format="MMM Y")
        else:
            name += format_date_cached(cache, date_start, date_format="Y") + " - " + format_date_cached(cache, date_end, date_format="Y")
        if structure_id:
            structure_id = self.env["hr.payroll.structure"].browse(structure_id)
            if structure_id.country_code:
                name += f" ({structure_id.country_code})"
        return name

    def _get_valid_versions(
        self,
        date_start=None,
        date_end=None,
        structure_id=None,
        company_id=None,
        employee_type_ids=None,
        employee_ids=None,
    ):
        date_start = date_start or self.date_start
        date_end = date_end or self.date_end
        version_domain = self._get_valid_versions_domain_payrun(date_start, date_end, structure_id, company_id, employee_type_ids)
        if employee_ids:
            version_domain &= Domain([('employee_id', 'in', employee_ids)])

        valid_versions = self.env["hr.version"]
        for versions in self.env["hr.employee"]._get_contracts(date_start, date_end, False, version_domain).values():
            valid_versions |= versions
        return valid_versions

    def _get_valid_versions_domain_payrun(self, date_start=None, date_end=None, structure_id=None, company_id=None, employee_type_ids=None):
        structure = self.env["hr.payroll.structure"].browse(structure_id) if structure_id else self.structure_id
        company = company_id or self.company_id.id
        version_domain = Domain([
            ('company_id', '=', company),
            ('employee_id', '!=', False),
            ('active_employee', '=', True),
            ('date_version', '<=', date_end),
            ('structure_type_id', '=', structure.type_id.id),
        ])
        allowed_employee_type_ids = set(employee_type_ids or [])
        if structure.employee_type_ids:
            struct_employee_type_ids = set(structure.employee_type_ids.ids)
            allowed_employee_type_ids = allowed_employee_type_ids & struct_employee_type_ids if allowed_employee_type_ids else struct_employee_type_ids
        if allowed_employee_type_ids:
            version_domain &= Domain([('employee_type_id', 'in', list(allowed_employee_type_ids))])
        return version_domain

    @api.depends('date_start', 'date_end', 'structure_id')
    def _compute_name(self):
        formated_date_cache = {}
        for payrun in self:
            if not payrun.name:
                payrun.name = payrun._get_name_for_period({
                    'date_start': payrun.date_start,
                    'date_end': payrun.date_end,
                    'structure_id': payrun.structure_id.id,
                    'employee_type_ids': payrun.employee_type_ids.ids,
                }, formated_date_cache)

    @api.depends('slip_ids')
    def _compute_version_ids(self):
        for payrun in self:
            if payrun.slip_ids or payrun.version_ids:
                versions_with_slips = payrun.slip_ids.version_id
                if versions_with_slips - payrun.version_ids:    # ADDED payslip
                    payrun.version_ids = payrun.version_ids | versions_with_slips
                elif payrun.state != '00_draft' and payrun.version_ids - versions_with_slips:  # REMOVED payslip
                    payrun.version_ids = versions_with_slips
            elif not payrun.version_ids:
                payrun.version_ids = payrun._get_valid_versions(employee_type_ids=payrun.employee_type_ids.ids)

    @api.depends("slip_ids")
    def _compute_payslip_count(self):
        for payslip_run in self:
            payslip_run.payslip_count = len(payslip_run.slip_ids)

    @api.depends("version_ids")
    def _compute_employee_count(self):
        self.env.cr.execute(
            """
            SELECT rel.hr_payslip_run_id AS id,
                   COUNT(DISTINCT v.employee_id) AS count
              FROM hr_payslip_run_hr_version_rel rel
              JOIN hr_version v
                ON rel.hr_version_id = v.id
             WHERE rel.hr_payslip_run_id IN %s
          GROUP BY rel.hr_payslip_run_id
            """, [tuple(self.ids)]
        )
        employee_count_per_payrun = dict(self.env.cr.fetchall())
        for payrun in self:
            payrun.employee_count = employee_count_per_payrun.get(payrun.id, 0)

    @api.depends("slip_ids.state", "version_ids")
    def _compute_state(self):
        for payslip_run in self:
            missing_slips = payslip_run.version_ids - payslip_run.slip_ids.version_id
            if missing_slips:
                payslip_run.state = '00_draft'
                continue
            states = payslip_run.mapped('slip_ids.state')
            if any(state == "draft" for state in states):
                payslip_run.state = '01_ready'
            elif any(state == "validated" for state in states):
                payslip_run.state = '02_close'
            elif any(state == "paid" for state in states):
                payslip_run.state = '03_paid'
            else:
                payslip_run.state = '04_cancel'

    @api.depends('state')
    def _compute_color(self):
        for payslip_run in self:
            payslip_run.color = STATUS_COLOR[payslip_run.state]

    @api.depends('structure_id', 'company_id')
    def _compute_date_start(self):
        payrun_groups = self.env['hr.payslip.run']._read_group(
            domain=[
                ('id', 'not in', self.ids),
                ('structure_id', 'in', self.structure_id.ids),
                ('company_id', 'in', self.company_id.ids),
                ('state', 'in', ['02_close', '03_paid']),
                ('slip_ids', 'any', [('is_refund_payslip', '=', False)]),
            ],
            groupby=['structure_id', 'company_id'],
            aggregates=['date_end:max']
        )
        date_end_by_structure_company = {
            (structure.id, company.id): date_end_max
            for structure, company, date_end_max in payrun_groups
        }

        for payslip_run in self:
            schedule_pay = payslip_run.structure_id.type_id.default_schedule_pay
            if schedule_pay:
                last_date_end = date_end_by_structure_company.get((payslip_run.structure_id.id, payslip_run.company_id.id))
                if last_date_end:
                    payslip_run.date_start = last_date_end + relativedelta(days=1)
                else:
                    payslip_run.date_start = self.env["hr.payslip"]._schedule_period_start(schedule_pay, date.today(), payslip_run.country_code)

    @api.depends('date_start')
    def _compute_date_end(self):
        for payslip_run in self:
            schedule_pay = payslip_run.structure_id.type_id.default_schedule_pay
            if schedule_pay:
                payslip_run.date_end = (payslip_run.date_start and payslip_run.date_start +
                                        self.env["hr.payslip"]._schedule_timedelta(schedule_pay, payslip_run.date_start, payslip_run.country_code))

    @api.depends("slip_ids.gross_wage", "slip_ids.net_wage", "slip_ids.state")
    def _compute_gross_net_sum(self):
        for payslip_run in self:
            payslip_run.gross_sum = sum(payslip_run.slip_ids.filtered(lambda p: p.state != "cancel").mapped("gross_wage"))
            payslip_run.net_sum = sum(payslip_run.slip_ids.filtered(lambda p: p.state != "cancel").mapped("net_wage"))

    @api.depends('employee_type_ids', 'country_id')
    def _compute_structure_domain(self):
        for record in self:
            domain = Domain('country_id', 'in', [False, record.country_id.id])
            if record.employee_type_ids:
                employee_type_domain = Domain('employee_type_ids', 'in', [False] + record.employee_type_ids.ids)
                domain = Domain.AND([domain, employee_type_domain])
            record.structure_domain = domain

    @api.depends('slip_ids.error_count', 'slip_ids.warning_count')
    def _compute_payslips_with_warnings_and_errors(self):
        for run in self:
            run.payslips_with_warnings = sum(run.slip_ids.mapped('warning_count'))
            run.payslips_with_errors = sum(run.slip_ids.mapped('error_count'))

    @api.depends('slip_ids.line_ids')
    def _compute_empty_payslips(self):
        for run in self:
            run.empty_payslips = len(run.slip_ids.filtered(
                lambda slip: not slip.line_ids
            ))

    def _search_country_id(self, operator, value):
        return [('company_id.partner_id.country_id', operator, value)]

    def action_draft(self):
        if self.slip_ids.filtered(lambda s: s.state == 'paid'):
            raise ValidationError(self.env._('You cannot reset a pay run to draft if some of the payslips have already been paid.'))
        self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'hr.payslip.run'),
            ('res_id', 'in', self.ids),
            ('res_field', '=', 'payment_report')
        ]).unlink()
        self.write({
            'payment_report': False,
            'payment_report_filename': False,
            'payment_report_format': False,
            'payment_report_date': False,
        })
        self.slip_ids.write({
            'state': 'draft',
        })

    def action_payment_report(self, export_format='csv'):
        self.ensure_one()
        valid_version_ids = self.slip_ids.version_id.ids
        payslip_domain = Domain.AND([
        Domain('version_id', 'in', valid_version_ids),
        Domain('state', '=', 'validated'),
        ])
        unpaid_payslips = self.env['hr.payslip'].search(payslip_domain).ids

        return {
            'name': self.env._('Pay'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.payment.report.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_payslip_ids': self.slip_ids.ids,
                'default_payslip_run_id': self.id,
                'default_export_format': export_format,
                'default_unpaid_payslips': unpaid_payslips,
                'default_allowed_unpaid_payslip_ids': unpaid_payslips,
            },
        }

    def action_paid(self):
        self.mapped('slip_ids').action_payslip_paid()

    def action_unpaid(self):
        self.slip_ids.action_payslip_unpaid()

    def action_correct(self):
        self.ensure_one()
        if self.state not in ('02_close', '03_paid'):
            raise UserError(self.env._("You can only correct a validated or paid pay run."))

        original_slips = self.slip_ids.filtered(lambda s: not s.is_refund_payslip)

        correction_run = self.create({
            'name': self.env._("%s (Correction)", self.name),
            'date_start': self.date_start,
            'date_end': self.date_end,
            'structure_id': self.structure_id.id,
            'company_id': self.company_id.id,
        })

        reverted_payslips = original_slips._action_refund_payslips()
        corrected_payslips = original_slips._action_correct_payslips()

        (reverted_payslips | corrected_payslips).write({'payslip_run_id': correction_run.id})

        correction_run.version_ids = original_slips.version_id

        return correction_run.action_open_payslips()

    def action_validate(self):
        if not (self.env.user.has_group('hr_payroll.group_hr_payroll_officer') or
                self.env.user.has_group('base.group_system') or self.env.is_superuser()):
            if self.payslips_with_warnings > 0 or self.payslips_with_errors > 0:
                raise UserError(self.env._(
                    "You do not have sufficient permissions to validate a Pay Run with warnings or errors.\n"
                    "Please ask a Payroll Officer or Manager to review."
                ))
        return self.slip_ids.filtered(
            lambda slip: slip.state != 'cancel' and slip.line_ids
        ).action_payslip_done()

    def action_confirm(self):
        self.slip_ids.filtered(lambda slip: slip.state == 'draft').compute_sheet()

    def action_add_employees(self):
        self.ensure_one()
        action = self.action_payroll_hr_version_list_view_payrun()
        action.update({
            'context': {
                'payrun_id': self.id,
                'payrun_kanban_card_view_id': False,
            },
            'domain': Domain.AND([
                action.get('domain', []),
                Domain('id', 'not in', self.version_ids.ids)
            ])
        })
        return action

    def action_open_payslips(self):
        self.ensure_one()
        if self.state == '00_draft':
            self._generate_payslips()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_payroll.action_view_hr_payslip_month_form')
        action['domain'] = Domain.AND([
            action.get('domain') or [],
            Domain('payslip_run_id', '=', self.id),
        ])
        action['context'] = dict(
            literal_eval(action["context"]),
            payrun_kanban_card_view_id=self.env.ref('hr_payroll.hr_payrun_payslip_kanban_card_view').id)
        action['display_name'] = self.name
        return action

    def action_generate_payslips_pdf_send_by_email(self):
        return self.slip_ids.with_context({'pdf_generation_message': self.env._("PDFs are generated and sent by email")}).action_generate_pdf()

    def action_generate_payslips_pdf(self):
        self.slip_ids.with_context({'is_test_print': True}).action_generate_pdf()

    @api.model
    def _get_start_payrun_warnings(self, versions, date_start, date_end):
        """ Check for the most common issues before starting a brand new pay
        run (missing employee data, pending time offs, no time off recorded). """
        warnings = []
        if versions.filtered(lambda v: v.review_state in ('2_to_review', '3_anomaly')):
            warnings.append({
                'title': self.env._("Employees to Review"),
                'body': self.env._("Fix missing or incorrect employee data before finalizing payslips."),
                'reviewLabel': self.env._("Review Employees"),
                'reviewAction': {
                    'name': self.env._('Employee'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'list',
                    'views': [(self.env.ref("hr_payroll.view_employee_tree").id, 'list')],
                    'res_model': 'hr.employee',
                    'domain': Domain('id', 'in', versions.employee_id.ids),
                    'search_view_id': [self.env.ref("hr_payroll.view_employee_filter").id, 'search'],
                    'context': {
                        'search_default_to_review': True,
                        'search_default_anomalies': True,
                    },
                },
            })
        time_to_review_domain = Domain.AND([
            Domain.OR([
                Domain.AND([
                    Domain('employee_id', 'in', versions.employee_id.ids),
                    Domain('payslip_state', '!=', 'done'),
                    Domain('date_from', '<=', date_end),
                ]),
                Domain.AND([
                    Domain('employee_id', 'in', versions.employee_id.ids),
                    Domain('state', 'in', ['confirm', 'validate1', 'validate']),
                    Domain('date_from', '<=', date_end),
                    Domain('date_to', '>=', date_start),
                ]),
            ]),
            Domain.OR([
                Domain('state', 'in', ['confirm', 'validate1']),
                Domain('payslip_state', '=', 'blocked'),
            ]),
            Domain('state', 'not in', ('refuse', 'cancel')),
        ])
        if self.env['hr.leave'].search_count(time_to_review_domain, limit=1):
            warnings.append({
                'title': self.env._("Time Offs to Review"),
                'body': self.env._("There are still time offs to approve."),
                'reviewLabel': self.env._("Review Time"),
                'reviewAction': {
                    'name': self.env._('Time Offs to Review'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'list,form',
                    'views': [(False, 'list'), (False, 'form')],
                    'res_model': 'hr.leave',
                    'domain': time_to_review_domain,
                },
            })
        time_versions = versions.filtered(lambda v: v.has_static_work_entries())
        no_time_off_domain = Domain.AND([
            Domain('employee_id', 'in', time_versions.employee_id.ids),
            Domain('state', 'not in', ('refuse', 'cancel')),
        ])
        if time_versions and not self.env['hr.leave'].search_count(no_time_off_domain & Domain([
            ('date_from', '<=', date_end), ('date_to', '>=', date_start),
        ]), limit=1):
            warnings.append({
                'title': self.env._("No Time Offs"),
                'body': self.env._(
                    "There is no time off for the period.\n"
                    "Looks good, everybody is working. Or did you forget to record them?"
                ),
                'reviewLabel': self.env._("Record Time"),
                'reviewAction': {
                    'name': self.env._('Time Off'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'gantt,list,kanban',
                    'views': [(self.env.ref("hr_holidays_gantt.hr_leave_gantt_view_payroll").id, 'gantt'), (False, 'list'), (False, 'kanban')],
                    'search_view_id': [self.env.ref("hr_holidays.hr_leave_view_search_manager").id, 'search'],
                    'res_model': 'hr.leave',
                    'domain': no_time_off_domain,
                    'context': {
                        'initialDate': str(date_start),
                        'hide_employee_name': 1,
                    },
                },
            })
        return warnings

    @api.model
    def action_start_payrun_with_warnings(self, vals):
        vals = dict(vals)
        date_start = fields.Date.from_string(vals.get('date_start'))
        date_end = fields.Date.from_string(vals.get('date_end'))
        versions = self._get_valid_versions(
            date_start, date_end, vals.get('structure_id'), vals.get('company_id'), vals.get('employee_type_ids'),
        )
        warnings = self._get_start_payrun_warnings(versions, date_start, date_end)
        if warnings:
            return {
                'type': 'ir.actions.client',
                'tag': 'hr_payroll.payrun_start_warning',
                'params': {
                    'warnings': warnings,
                    'createVals': vals,
                },
            }
        return self.action_start_payrun(vals)

    @api.model
    def action_start_payrun(self, vals):
        return self.create(vals).action_open_payslips()

    def action_add_versions(self, employee_ids):
        self.ensure_one()
        valid_versions = self._get_valid_versions(employee_ids=employee_ids)
        self.version_ids = [Command.link(vid) for vid in valid_versions.ids]

    def action_assign_versions(self, employee_ids):
        self.ensure_one()
        valid_versions = self._get_valid_versions(employee_ids=employee_ids)
        self.version_ids = [Command.set(valid_versions.ids)]

    def action_payroll_hr_version_list_view_payrun(
        self,
        date_start=None,
        date_end=None,
        structure_id=None,
        company_id=None,
        employee_type_ids=None,
    ):
        action = self.env['ir.actions.act_window']._for_xml_id('hr_payroll.action_view_employee_tree')

        valid_versions = self._get_valid_versions(
            fields.Date.from_string(date_start),
            fields.Date.from_string(date_end),
            structure_id,
            company_id,
            employee_type_ids,
        )
        filtered_versions = valid_versions - self.version_ids
        action['domain'] = [("id", "in", filtered_versions.employee_id.ids)]
        return action

    def action_review_issues(self):
        self.ensure_one()
        return {
            'name': 'Issue Payslips',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'context': {
                'search_default_payslip_run_id': self.id,
                'search_default_filter_issue': 1,
            }
        }

    def _generate_payslips(self):
        self.ensure_one()

        if not self.version_ids:
            raise UserError(self.env._("You must have employee records in the payrun to generate payslip(s)."))

        valid_versions = self.version_ids - self.slip_ids.version_id
        if self.structure_id:
            valid_versions = valid_versions.filtered(lambda c: c.structure_type_id.id == self.structure_id.type_id.id)

        payslips_vals = []
        for version in valid_versions:
            values = {
                'employee_id': version.employee_id.id,
                'payslip_run_id': self.id,
                'date_from': self.date_start,
                'date_to': self.date_end,
                'version_id': version.id,
                'company_id': self.company_id.id,
                'struct_id': self.structure_id.id or version.structure_type_id.default_struct_id.id,
            }
            payslips_vals.append(values)
        Payslip = self.env['hr.payslip']
        # A large pay run logs one creation message per payslip.
        # This parameter skips them for databases where that cost is not worth the traceability.
        if self.env['ir.config_parameter'].sudo().get_bool('hr_payroll.payslip_run_creation_no_message'):
            Payslip = Payslip.with_context(mail_create_nolog=True)
        new_payslips = Payslip.create(payslips_vals)
        new_payslips._compute_name()
        new_payslips.compute_sheet()
        return new_payslips

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft_or_cancel(self):
        if any(self.mapped('slip_ids').filtered(lambda payslip: payslip.state not in ('draft', 'cancel'))):
            raise UserError(self.env._("You can't delete a pay run with payslips if they are not draft or cancelled."))

    def _are_payslips_ready(self):
        return any(slip.state in ['validated', 'cancel'] for slip in self.mapped('slip_ids'))

    @api.model
    def get_unusual_days(self, date_from, date_to=None):
        return self.env.company.resource_calendar_id._get_unusual_days(
            datetime.combine(fields.Date.from_string(date_from), time.min, tzinfo=UTC),
            datetime.combine(fields.Date.from_string(date_to), time.max, tzinfo=UTC),
            self.company_id,
        )

    def get_record_default_action(self, access_uid=None):
        return self.action_open_payslips()

    @api.depends('slip_ids.employer_cost')
    def _compute_total_employer_cost(self):
        for payslip_run in self:
            payslip_run.total_employer_cost = sum(payslip_run.slip_ids.filtered(lambda p: p.state != "cancel").mapped("employer_cost"))

    def _get_last_three_payruns(self):
        """
            Get the payruns from the last payment periods including the current one,
            of the same structure and company, Also try to filter correction ones.
        """
        res = self

        prev_two_payruns = self.search([
            ('id', '!=', self.id),
            ('structure_id', '=', self.structure_id.id),
            ('company_id', '=', self.company_id.id),
            ('date_start', '<=', self.date_start),
            ('state', 'in', ['02_close', '03_paid']),
            ('slip_ids', 'any', [('is_refund_payslip', '=', False)]),
        ], order="date_start desc", limit=2)

        if prev_two_payruns:
            res = prev_two_payruns + res

        return res

    def action_work_time_report(self):
        self.ensure_one()
        last_three_payruns = self._get_last_three_payruns()

        action = self.env['ir.actions.act_window']._for_xml_id('hr_payroll.hr_payslip_work_days_action_report')
        action['context'] = {
            'search_default_group_by_code': True,
        }
        action['domain'] = [('payslip_run_id', 'in', last_three_payruns.ids)]
        return action

    def action_payroll_line_report(self):
        self.ensure_one()
        last_three_payruns = self._get_last_three_payruns()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_payroll.hr_payslip_line_action_report')
        action['context'] = {
            'search_default_salary_rule_id': True,
            'search_default_payslip_run_id': self.id,
            'is_payslip_line_report': True,
        }
        action['domain'] = [('payslip_run_id', 'in', last_three_payruns.ids)]
        return action

    def action_re_compute_payslips(self):
        self.ensure_one()
        if self.state not in ['00_draft', '01_ready']:
            raise UserError(self.env._("You can only re-compute payslips in a pay run that is in draft or ready state."))
        self.slip_ids.filtered(lambda slip: slip.state == 'draft').compute_sheet()

    def off_cycle_version(self, version_id):
        self.ensure_one()
        self.write({'version_ids': [Command.unlink(version_id)]})
        payslips = self.slip_ids.filtered_domain([('version_id', '=', version_id)])
        if payslips:
            payslips.payslip_run_id = Command.unlink(self.id)
        self.flush_model(['version_ids', 'slip_ids'])
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def _cron_generate_payrun_for_employee_types_with_auto_post(self):
        employee_types_with_auto_post = self.env['hr.employee.type'].search([('payroll_auto_post', '=', True)])
        if not employee_types_with_auto_post:
            return

        companies = self.env.companies
        today = fields.Date.context_today(self)
        payruns_data = {}

        for employee_type in employee_types_with_auto_post:
            payrun_closing_day = int(employee_type.payroll_closing_date)
            month_offset = -1 if payrun_closing_day < 10 else 0
            payrun_closing_date = today + relativedelta(months=month_offset, day=payrun_closing_day)

            if payrun_closing_date > today:
                payrun_closing_date += relativedelta(months=-1)

            date_start = payrun_closing_date.replace(day=1)
            date_end = (date_start + relativedelta(months=1)) - relativedelta(days=1)

            payruns_data[employee_type.id] = {
                'date_start': date_start,
                'date_end': date_end,
                'employee_type': employee_type,
            }

        if not payruns_data:
            return

        min_date_start = min(val['date_start'] for val in payruns_data.values())
        max_date_end = max(val['date_end'] for val in payruns_data.values())

        existing_payruns = {
            (
                payrun.company_id.id,
                payrun.date_start,
                payrun.date_end,
                employee_type.id,
            )
            for payrun in self.search([
                ('date_start', '>=', min_date_start),
                ('date_end', '<=', max_date_end),
                ('employee_type_ids', 'in', payruns_data.keys()),
                ('state', '!=', '04_cancel'),
                ('company_id', 'in', companies.ids),
            ])
            for employee_type in payrun.employee_type_ids
        }

        for company in companies:
            default_struct = self.env['hr.version'].with_company(company)._default_salary_structure().default_struct_id

            for values in payruns_data.values():
                employee_type = values['employee_type']
                if employee_type.country_id and employee_type.country_id != company.country_id:
                    continue

                date_start = values['date_start']
                date_end = values['date_end']

                key = (company.id, date_start, date_end, employee_type.id)
                if key in existing_payruns:
                    continue

                valid_versions = self._get_valid_versions(
                    date_start,
                    date_end,
                    default_struct.id,
                    company.id,
                    employee_type.ids,
                )

                if not valid_versions:
                    continue

                payrun = self.create({
                    'name': self._get_name_for_period({
                        'date_start': date_start,
                        'date_end': date_end,
                        'employee_type_ids': [employee_type.id],
                        'structure_id': default_struct.id,
                    }),
                    'date_start': date_start,
                    'date_end': date_end,
                    'employee_type_ids': [employee_type.id],
                    'structure_id': default_struct.id,
                    'company_id': company.id,
                    'version_ids': valid_versions.ids,
                })

                payrun._generate_payslips()
                payrun.action_validate()

    def action_move_to_off_cycle(self, employee_id):
        versions = self.version_ids.filtered(lambda v: v.employee_id.id == employee_id)
        if versions:
            self.write({'version_ids': [Command.unlink(v.id) for v in versions]})
        payslips = self.slip_ids.filtered(lambda s: s.version_id in versions)
        if payslips:
            self.write({'slip_ids': [Command.unlink(payslips.ids)]})
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}
