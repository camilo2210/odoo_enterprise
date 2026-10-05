# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime
from collections import defaultdict
import json
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, modules
from odoo.models import MAGIC_COLUMNS
from odoo.tools import float_round, html_sanitize, config
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import format_date


class HrVersion(models.Model):
    _inherit = 'hr.version'
    _description = 'Employee Contract'

    schedule_pay = fields.Selection(
        selection=lambda self: self.env['hr.payroll.structure.type']._get_selection_schedule_pay(),
        compute='_compute_schedule_pay', store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user", default='monthly', string='Pay Schedule')
    show_schedule_pay = fields.Boolean(compute='_compute_show_schedule_pay', groups="hr.group_hr_user")
    resource_calendar_id = fields.Many2one(default=lambda self: self.env.company.resource_calendar_id,
        help="Employee's working schedule."
    )
    fixed_term = fields.Boolean(tracking=1)
    trial_date_end = fields.Date(tracking=1)
    date_start = fields.Date(tracking=1)
    date_end = fields.Date(tracking=1)
    wage = fields.Monetary(groups="hr_payroll.group_hr_payroll_user", tracking=1)
    is_current = fields.Boolean(tracking=1)
    is_past = fields.Boolean(tracking=1)
    is_future = fields.Boolean(tracking=1)
    is_in_contract = fields.Boolean(tracking=1)
    structure_type_id = fields.Many2one(groups="hr_payroll.group_hr_payroll_user", tracking=1)
    employee_type_id = fields.Many2one(groups="hr.group_hr_manager,hr_payroll.group_hr_payroll_user", tracking=1)

    full_time_required_hours = fields.Float(related='resource_calendar_id.full_time_required_hours', groups="hr.group_hr_user")
    is_fulltime = fields.Boolean(related='resource_calendar_id.is_fulltime', groups="hr.group_hr_user")
    reference_calendar_id = fields.Many2one(related='resource_calendar_id.reference_calendar_id', readonly=False, groups="hr_payroll.group_hr_payroll_user")
    wage_type = fields.Selection([
        ('monthly', 'Fixed Wage'),
        ('hourly', 'Hourly Wage')
    ], compute='_compute_wage_type', store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user", tracking=1)
    hourly_wage = fields.Float('Hourly Wage', digits=(16, 4), tracking=1, help="Employee's hourly gross wage.", groups="hr_payroll.group_hr_payroll_user")
    payslips_count = fields.Integer("# Payslips", compute='_compute_payslips_count', groups="hr_payroll.group_hr_payroll_user")
    work_time_rate = fields.Float(
        compute='_compute_work_time_rate', store=True, readonly=True,
        string='Work time rate', help='Work time rate versus full time working schedule.', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    is_non_resident = fields.Boolean(string='Non-resident', help='If the employee is not a legal resident of the country where they are employed', groups="hr.group_hr_user", tracking=1)
    disabled = fields.Boolean(string="Disabled", help="If the employee is declared disabled by law", groups="hr_payroll.group_hr_payroll_user", tracking=1)

    structure_id = fields.Many2one(related='structure_type_id.default_struct_id', store=True, copy=True, groups="hr.group_hr_user", tracking=1)
    payroll_properties = fields.Properties('Payroll Properties', definition='structure_id.version_properties_definition', copy=True, precompute=False, readonly=False, groups="hr_payroll.group_hr_payroll_user")
    issues = fields.Json(compute='_compute_issues', groups="hr.group_hr_user,hr_payroll.group_hr_payroll_user")

    review_state = fields.Selection(related='employee_id.review_state', store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user")
    date_to_review = fields.Datetime(related='employee_id.date_to_review', store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user")

    departure_id = fields.Many2one(groups="hr_payroll.group_hr_payroll_user")
    departure_reason_id = fields.Many2one(groups="hr_payroll.group_hr_payroll_user")
    departure_description = fields.Html(groups="hr_payroll.group_hr_payroll_user")
    dismissal_date = fields.Date(groups="hr_payroll.group_hr_payroll_user")
    departure_action_date = fields.Date(groups="hr_payroll.group_hr_payroll_user")
    departure_apply_immediately = fields.Boolean(groups="hr_payroll.group_hr_payroll_user")
    departure_apply_date = fields.Date(groups="hr_payroll.group_hr_payroll_user")
    employee_issues = fields.Json(related="employee_id.issues", string="Employee Version Issues", groups="hr.group_hr_user,hr_payroll.group_hr_payroll_user", readonly=True)

    # todo : make this a belgian thing ?
    holidays = fields.Float(string='Extra Time Off', groups="hr.group_hr_user",
        help="Number of days of paid leaves the employee gets per year.", tracking=1)

    final_yearly_costs = fields.Monetary(
        compute='_compute_final_yearly_costs',
        inverse='_inverse_final_yearly_costs',
        readonly=False, store=True,
        string="Yearly Cost",
        tracking=1,
        aggregator="avg",
        groups="hr_payroll.group_hr_payroll_user")

    payslip_run_ids = fields.Many2many('hr.payslip.run', relation="hr_payslip_run_hr_version_rel", string="Pay Runs", groups="hr_payroll.group_hr_payroll_user")

    payroll_config_id = fields.Many2one(
        'payroll.config.settings',
        string="Payroll Config",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True,
        index='btree_not_null',
        compute='_compute_payroll_config_id',
        compute_sudo=True,
        store=True)

    _check_hourly_wage_positive = models.Constraint(
        'CHECK(hourly_wage >= 0)',
        'The hourly wage must be a positive value.',
    )

    @api.model
    def _benefit_white_list(self):
        return []

    @api.model
    def _get_sacrifice_fields(self):
        return ['holidays']

    @api.model
    def _benefit_black_list(self):
        return set(MAGIC_COLUMNS + ['wage', 'active'])

    def _get_yearly_cost_sacrifice_ratio(self):
        return 1.0 - self.holidays / 231.0

    def _get_yearly_cost_sacrifice_fixed(self):
        return 0.0

    def _get_yearly_cost_from_wage(self, fixed=None, ratio=None):
        self.ensure_one()
        ratio = self._get_yearly_cost_sacrifice_ratio() if ratio is None else ratio
        fixed = self._get_yearly_cost_sacrifice_fixed() if fixed is None else fixed
        return self._get_benefits_costs() + (self._get_salary_costs_factor() * self.wage / ratio) + fixed

    def _get_wage_from_yearly_costs(self, yearly_cost, ratio=None, fixed=None, benefits_cost=None):
        self.ensure_one()
        ratio = self._get_yearly_cost_sacrifice_ratio() if ratio is None else ratio
        fixed = self._get_yearly_cost_sacrifice_fixed() if fixed is None else fixed
        benefits_cost = self._get_benefits_costs() if benefits_cost is None else benefits_cost
        salary_costs_factor = self._get_salary_costs_factor()
        if salary_costs_factor:
            return (yearly_cost - fixed - benefits_cost) * ratio / salary_costs_factor
        return 0

    def _get_benefit_description(self, benefit, new_value=None):
        self.ensure_one()
        if hasattr(self, '_get_description_%s' % benefit.field):
            description = getattr(self, '_get_description_%s' % benefit.field)(new_value)
        else:
            description = benefit.description
        return html_sanitize(description)

    def _get_benefit_fields(self, triggers=True):
        types = ('float', 'integer', 'monetary', 'boolean', 'properties')
        if not triggers:
            types += ('text',)
        nonstored_whitelist = self._benefit_white_list()
        benefit_fields = {
            field.name
            for field in self._fields.values()
            if field.type in types and (field.store or not field.store and field.name in nonstored_whitelist) and not field.name.startswith("x_studio_")
        }
        if not triggers:
            benefit_fields |= {'wage'}
        return tuple(benefit_fields - self._benefit_black_list())

    def _get_benefits_costs(self):
        self.ensure_one()
        benefits = self.env['hr.contract.salary.benefit'].search([
            ('structure_type_id', '=', self.structure_type_id.id),
            ('cost_res_field_id', '!=', False),
        ])
        if not benefits:
            return 0
        monthly_benefits = benefits.filtered(lambda a: a.benefit_type_id.periodicity == 'monthly')
        monthly_cost = sum(self[benefit.cost_field] or 0 for benefit in monthly_benefits if benefit.cost_field in self)
        yearly_cost = sum(self[benefit.cost_field] or 0 for benefit in benefits - monthly_benefits if benefit.cost_field in self)
        return monthly_cost * 12 + yearly_cost

    def _get_employer_costs_from_gross(self, gross):
        self.ensure_one()
        return (gross * self._get_salary_costs_factor()) + self._get_benefits_costs()

    @api.depends(lambda self: (
        'wage',
        'structure_type_id.salary_benefits_ids.res_field_id',
        'structure_type_id.salary_benefits_ids.cost_res_field_id',
        *self._get_benefit_fields(),
        *self._get_sacrifice_fields()))
    def _compute_final_yearly_costs(self):
        for version in self:
            yearly_cost_from_wage = version._get_yearly_cost_from_wage()
            # avoid overwrite because of rounding issues.
            if abs(version.final_yearly_costs - yearly_cost_from_wage) > 0.10:
                version.final_yearly_costs = yearly_cost_from_wage

    def _inverse_final_yearly_costs(self):
        for version in self:
            version.wage = version._get_wage_from_yearly_costs(version.final_yearly_costs)

    @api.model
    def _issues_dependencies(self):
        return ['contract_date_start', 'contract_date_end', 'structure_type_id', 'employee_id.active']

    @api.depends(lambda self: self._issues_dependencies())
    def _compute_issues(self):
        self.issues = {}
        if (
            not self.env.registry.ready
            and not (config["test_enable"] or modules.module.current_test)
            # This context key acts as an escape hatch for upgrade scripts that need to
            # explicitly recompute payroll issues while the registry is still initializing.
            and not (self.env.context.get("hr_payroll_force_compute_issue"))
        ):
            return
        warnings = self.env["hr.payroll.warning"].search([
            ("display_on_model", "=", True),
            ("model_name", "in", ("hr.version", "hr.employee")),
            ("active", "=", True),
        ])
        if not warnings:
            return
        for warning in warnings:
            if warning.warning_type == 'domain':
                if warning.model_name == 'hr.version':
                    related_versions = warning._get_warning_domain_records(self.company_id, records_to_check=self)
                else:
                    related_versions = warning._get_warning_domain_records(self.company_id, records_to_check=self.employee_id).version_ids
                for version in self:
                    issues = version.issues or {}
                    if version in related_versions:
                        issues[len(issues)] = warning._get_warning_issue()
                    version.issues = issues
            else:
                if warning.model_name == 'hr.version':
                    related_versions, warning_details, _, _ = warning._get_warning_python_records(localdict={'active_ids': self.ids})
                    if related_versions == self.env['base']:
                        continue
                else:
                    related_emps, warning_details, _, _ = warning._get_warning_python_records(localdict={'active_ids': self.employee_id.ids})
                    if related_emps == self.env['base']:
                        continue
                    related_versions = related_emps.version_ids
                for version in self:
                    issues = version.issues or {}
                    if version in related_versions:
                        if warning_details:
                            for detail in warning_details.get(version, []):
                                issues[len(issues)] = detail
                        else:
                            issues[len(issues)] = warning._get_warning_issue()
                    version.issues = issues

    def _get_missing_payrun_issue_values(self, payruns):
        if len(payruns) > 1:
            date_start = payruns[0].date_start
            date_end = payruns[0].date_end
            if date_start.month == date_end.month and date_start.year == date_end.year:
                period_str = format_date(self.env, date_start, date_format='MMMM y')
            else:
                period_str = "%s - %s" % (
                    format_date(self.env, date_start, date_format='MMM d'),
                    format_date(self.env, date_end, date_format='MMM d, y')
                )
            return {
                "message": self.env._("The employee is not in any pay run for %s") % period_str,
                "level": "warning",
                "action_text": self.env._("View Pay Runs"),
                "action": {
                    "type": "ir.actions.act_window",
                    "name": self.env._("Pay Runs"),
                    "res_model": "hr.payslip.run",
                    "views": [[self.env.ref("hr_payroll.hr_payrun_payslip_kanban_card_view").id, "kanban"], [False, "list"]],
                    "domain": [('id', 'in', payruns.ids)],
                    "context": {
                        "group_by": ["state"],
                    },
                }
            }
        return {
            "message": self.env._("The pay run %s is missing this employee") % payruns.name,
            "level": "warning",
            "action_text": self.env._("Add payslip to Pay Run"),
            "action": {
                "type": "object",
                "name": "action_add_payslip_to_payrun",
                "args": json.dumps([payruns.id]),
            },
        }

    def _get_missing_payrun_by_version(self):
        versions_with_contract = self.filtered(lambda e: e.contract_date_start)
        if not versions_with_contract:
            return {}

        min_start = min(e.contract_date_start.replace(day=1) for e in versions_with_contract)
        max_end = False if any(not d for d in versions_with_contract.mapped('contract_date_end')) else max(
            e.contract_date_end + relativedelta(day=31) for e in versions_with_contract
        )
        payrun_domain = Domain.AND([
            Domain('date_end', '>=', min_start),
            Domain('company_id', 'in', versions_with_contract.company_id.ids),
            Domain.OR([
                Domain('structure_id', '=', False),
                Domain('structure_id.type_id', 'in', versions_with_contract.structure_type_id.ids),
            ]),
            Domain('employee_type_ids', 'in', [False] + versions_with_contract.employee_type_id.ids),
            Domain('state', 'in', ['00_draft', '01_ready']),
        ])
        if max_end:
            payrun_domain = Domain.AND([payrun_domain, Domain('date_start', '<=', max_end)])
        related_payruns = self.env['hr.payslip.run'].search(payrun_domain, order='date_start asc')

        if not related_payruns:
            return {}

        payslips_by_employee_and_payrun = {
            (employee, payrun): payslip for employee, payrun, payslip in self.env['hr.payslip']._read_group(
            domain=[('employee_id', 'in', versions_with_contract.employee_id.ids)],
            groupby=['employee_id', 'payslip_run_id'],
            aggregates=['id:recordset'])
        }
        empty_payrun = self.env['hr.payslip.run']
        missing_payruns_by_version = {}

        for version in versions_with_contract:
            version_payruns_domain = Domain.AND([
                Domain('date_end', '>=', version.contract_date_start.replace(day=1)),
                Domain.OR([
                    Domain('structure_id', '=', False),
                    Domain('structure_id.type_id', 'in', version.structure_type_id.ids),
                ]),
                Domain('company_id', '=', version.company_id.id),
            ])
            if version.contract_date_end:
                version_payruns_domain = Domain.AND([
                    version_payruns_domain,
                    Domain('date_start', '<=', version.contract_date_end + relativedelta(day=31)),
                ])
            version_payruns = related_payruns.filtered_domain(version_payruns_domain)

            if not version_payruns:
                continue

            # Group payruns by date range (handles all pay schedules)
            payruns_by_period = {}
            for payrun in version_payruns:
                period_key = (payrun.date_start, payrun.date_end)
                payruns_by_period[period_key] = payruns_by_period.get(period_key, self.env['hr.payslip.run']) | payrun

            off_cycle_payslips = payslips_by_employee_and_payrun.get((version.employee_id, empty_payrun), self.env['hr.payslip'])
            missing_payruns = []

            today = fields.Date.context_today(self)
            for (date_start, date_end), payruns in payruns_by_period.items():
                # Skip if employee has payslip in any payrun of this period
                if any(payslips_by_employee_and_payrun.get((version.employee_id, pr)) for pr in payruns):
                    continue
                # Skip if off-cycle payslip overlaps with this period
                if any(payslip.date_from <= date_end and payslip.date_to >= date_start for payslip in off_cycle_payslips):
                    continue

                payrun_closing_day = int(version.company_id.payroll_closing_date) if version.company_id.payroll_closing_date else None
                if payrun_closing_day:
                    month_offset = 1 if payrun_closing_day <= 9 else 0
                    period_closing_date = date_end + relativedelta(months=month_offset, day=payrun_closing_day)
                    if today < period_closing_date:
                        continue

                missing_payruns.append(payruns)

            if missing_payruns:
                missing_payruns_by_version[version] = missing_payruns

        return missing_payruns_by_version

    @api.constrains('contract_date_start', 'contract_date_end', 'departure_id')
    def _check_contract_dates(self):
        per_version_domains = []
        for version in self.filtered(lambda v: not v.departure_id and v.contract_date_start):
            date_conflict = Domain('date_from', '<', version.contract_date_start)
            if version.contract_date_end:
                date_conflict |= Domain('date_to', '>', version.contract_date_end)
            per_version_domains.append(Domain('version_id', '=', version.id) & date_conflict)

        if not per_version_domains:
            return

        conflicting_payslips = self.env['hr.payslip'].search(
            Domain([
                ('state', 'in', ['validated', 'paid']),
                ('is_refunded', '=', False),
                ('is_refund_payslip', '=', False),
            ])
            & Domain.OR(per_version_domains)
        )
        if conflicting_payslips:
            action = self.env["ir.actions.actions"]._for_xml_id("hr_payroll.action_view_hr_payslip_month_form")
            action['domain'] = [('id', 'in', conflicting_payslips.ids)]
            raise RedirectWarning(
                self.env._(
                    "Payslips for this contract period have already been validated and not yet refunded. "
                    "Please refund the related payslips before modifying the contract dates."
                ),
                action,
                self.env._("View Payslips to Refund"),
            )

    @api.depends('structure_type_id')
    def _compute_schedule_pay(self):
        for version in self:
            if version.structure_type_id:
                version.schedule_pay = version.structure_type_id.default_schedule_pay

    @api.depends('structure_type_id')
    def _compute_wage_type(self):
        for version in self:
            version.wage_type = version.structure_type_id.wage_type

    @api.depends('resource_calendar_id.hours_per_week', 'resource_calendar_id.work_time_rate', 'company_id.resource_calendar_id.hours_per_week', 'reference_calendar_id.hours_per_week')
    def _compute_work_time_rate(self):
        for version in self:
            ref_calendar = version._get_reference_calendar()
            ref_hours = ref_calendar.hours_per_week if ref_calendar else 0
            version.work_time_rate = float_round(version.resource_calendar_id.hours_per_week / ref_hours, precision_digits=2) if ref_hours else 0

    def _compute_show_schedule_pay(self):
        number_of_possibilities = len(self.env['hr.payroll.structure.type']._get_selection_schedule_pay())
        for version in self:
            version.show_schedule_pay = number_of_possibilities > 1

    def _compute_payslips_count(self):
        count_data = self.env['hr.payslip']._read_group(
            [('version_id', 'in', self.ids)],
            ['version_id'],
            ['__count'])
        mapped_counts = {version.id: count for version, count in count_data}
        for version in self:
            version.payslips_count = mapped_counts.get(version.id, 0)

    @api.depends('company_id.payroll_config_ids.date_version', 'date_version')
    def _compute_payroll_config_id(self):
        for version in self:
            new_config = version.company_id._get_payroll_config(version.date_version)
            if new_config != version.payroll_config_id:
                version.payroll_config_id = new_config

    def _get_property_input_value(self, code):
        self.ensure_one()
        rule = self.env['hr.salary.rule'].search([('code', '=', code), ('struct_ids', 'in', self.structure_id.id)], limit=1)
        if rule:
            return dict(self.payroll_properties).get(rule.code, 0.00)
        return 0.0

    def _set_property_input_value(self, code, value):
        self.ensure_one()
        current_properties = dict(self.payroll_properties)
        rule = self.env['hr.salary.rule'].search([('code', '=', code), ('struct_ids', 'in', self.structure_id.id)], limit=1)
        if rule:
            rule_code_str = str(rule.code)
            definition = self.structure_id.version_properties_definition or []
            if not any(d.get('name') == rule_code_str for d in definition):
                raise ValidationError(
                    self.env._("Cannot set value for '%(rule)s': no version property definition found for this salary rule.", rule=rule.name)
                )
            current_properties.update({
                rule.code: value
            })
            self.write({
                'payroll_properties': current_properties
            })

    def _get_salary_costs_factor(self):
        self.ensure_one()
        factors = {
            "annually": 1,
            "semi-annually": 2,
            "quarterly": 4,
            "bi-monthly": 6,
            "monthly": 12,
            "semi-monthly": 24,
            "bi-weekly": 26,
            "weekly": 52,
            "daily": 52 * (self.resource_calendar_id.days_per_week or self.company_id.resource_calendar_id.days_per_week or 5),
        }
        return factors.get(self.schedule_pay, super()._get_salary_costs_factor())

    def _is_same_occupation(self, version):
        self.ensure_one()
        employee_type = self.employee_type_id
        work_time_rate = self.resource_calendar_id.work_time_rate
        return employee_type == version.employee_type_id and work_time_rate == version.resource_calendar_id.work_time_rate

    def _get_occupation_dates(self, include_future_contracts=False):
        # Takes several versions and returns all the versions under the same occupation (i.e. the same
        # work rate + the date_from and date_to)
        # include_future_contracts will use versions where the version_date_start is posterior
        # compared to today's date
        result = []
        done_versions = self.env['hr.version']
        date_today = fields.Date.context_today(self)

        def remove_gap(version, other_versions, before=False):
            # We do not consider a gap of more than 4 days to be a same occupation
            # other_versions is considered to be ordered correctly in function of `before`
            current_date = version.date_start if before else version.date_end
            for i, other_version in enumerate(other_versions):
                if not current_date:
                    return other_versions[0:i]
                if before:
                    gap = (current_date - other_version.date_end).days
                    current_date = other_version.date_start
                else:
                    gap = (other_version.date_start - current_date).days
                    current_date = other_version.date_end
                if gap >= 4:
                    return other_versions[0:i]
            return other_versions

        for version in self.with_context(active_test=True):
            if version in done_versions:
                continue
            versions = version  # hr.version(38,)
            date_from = version.date_start
            date_to = version.date_end
            all_versions = version.employee_id.version_ids.filtered(
                lambda c:
                c != version and
                (c.date_start <= date_today or include_future_contracts)
            ).sorted('date_start', reverse=True)  # hr.version(29, 37, 38, 39, 41) -> hr.version(29, 37, 39, 41)
            before_versions = all_versions.filtered(lambda c: c.date_start < version.date_start)  # hr.version(39, 41)
            before_versions = remove_gap(version, before_versions, before=True)
            after_versions = all_versions.filtered(lambda c: c.date_start > version.date_start).sorted(key='date_start')  # hr.version(37, 29)
            after_versions = remove_gap(version, after_versions)

            for before_version in before_versions:
                if version._is_same_occupation(before_version):
                    date_from = before_version.date_start
                    versions |= before_version
                else:
                    break

            for after_version in after_versions:
                if version._is_same_occupation(after_version):
                    date_to = after_version.date_end
                    versions |= after_version
                else:
                    break
            result.append((versions, date_from, date_to))
            done_versions |= versions
        return result

    def _get_normalized_wage(self):
        wage = self._get_contract_wage()
        if self.wage_type == 'hourly' or not self.resource_calendar_id.hours_per_week:
            return wage
        return wage * self._get_salary_costs_factor() / 52 / self.resource_calendar_id.hours_per_week

    def _get_contract_wage_field(self):
        self.ensure_one()
        if self.wage_type == 'hourly':
            return 'hourly_wage'
        return super()._get_contract_wage_field()

    def action_open_payslips(self):
        # [XBO] TODO: to remove if we don't want to display the button in the list view of version
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr_payroll.action_view_hr_payslip_month_form")
        action.update({'domain': [('version_id', '=', self.id)]})
        return action

    def _preprocess_work_hours_data(self, work_data, date_from, date_to):
        """
        Method is meant to be overriden, see hr_payroll_attendance
        """
        return

    def get_work_hours(self, date_from, date_to, work_entries_vals):
        # Get work hours between 2 dates (datetime.date)
        # To correctly englobe the period, the start and end periods are converted
        # using the calendar timezone.
        assert not isinstance(date_from, datetime)
        assert not isinstance(date_to, datetime)

        work_data = defaultdict(int)

        versions_by_company = defaultdict(lambda: self.env['hr.version'])
        for version in self:
            versions_by_company[version.company_id] += version

        # We don't need the timezone immediately here, but we need the uniqueness
        # of the key so that we can guarantee one timezone per set of versions.
        for company, versions in versions_by_company.items():
            work_data_tz = versions.with_company(company).sudo()._get_work_hours(date_from, date_to, work_entries_vals)
            for work_entry_type_id, hours in work_data_tz.items():
                work_data[work_entry_type_id] += hours
        return work_data

    def _get_work_hours(self, date_from, date_to, work_entries_vals):
        """
        Returns the amount (expressed in hours) of work
        for a version between two dates.
        If called on multiple versions, sum work amounts of each version.

        :param date_from: The start date
        :param date_to: The end date
        :returns: a dictionary {work_entry_id: hours_1, work_entry_2: hours_2}
        """
        assert not isinstance(date_from, datetime)
        assert not isinstance(date_to, datetime)

        version_ids = set(self.ids)
        filtered_work_entries = [
            work_entry_vals for work_entry_vals in work_entries_vals
            if work_entry_vals['version_id'].id in version_ids
            and date_from <= work_entry_vals['date'] <= date_to
        ]
        work_entries = defaultdict(lambda: 0)
        for work_entry_vals in filtered_work_entries:
            category_options = work_entry_vals.get('category_options_ids', self.env['hr.salary.rule.category']).sorted()
            work_entries[work_entry_vals['work_entry_type_id'], category_options] += work_entry_vals['duration']

        work_data = defaultdict(int)
        work_data.update(dict(work_entries))
        self._preprocess_work_hours_data(work_data, date_from, date_to)
        return work_data

    def _get_default_work_entry_type_id(self):
        return self.structure_type_id.default_work_entry_type_id.id or super()._get_default_work_entry_type_id()

    def _get_fields_that_recompute_payslip(self):
        # Returns the fields that should recompute the payslip
        return ['wage', 'hourly_wage', 'payroll_properties']

    def _get_nearly_expired_contracts(self, outdated_days, company_id=False):
        nearly_expired_versions = self.search([
            ('company_id', '=', company_id or self.env.company.id),
            ('contract_date_end', '>=', 'today'),
            ('contract_date_end', '<', outdated_days)])

        # Check if no new contracts starting after the end of the expiring one
        nearly_expired_versions_without_new_versions = self.env['hr.version']
        new_versions_grouped_by_employee = {
            employee.id
            for [employee] in self._read_group([
                ('company_id', '=', company_id or self.env.company.id),
                ('contract_date_start', '>=', outdated_days),
                ('employee_id', 'in', nearly_expired_versions.employee_id.ids)
            ], groupby=['employee_id'])
        }

        for expired_version in nearly_expired_versions:
            if expired_version.employee_id.id not in new_versions_grouped_by_employee:
                nearly_expired_versions_without_new_versions |= expired_version
        return nearly_expired_versions_without_new_versions

    @api.model
    def _get_whitelist_fields_from_template(self):
        return super()._get_whitelist_fields_from_template() + ['payroll_properties', 'hourly_wage']

    def _get_valid_payslips_count(self):
        return self.env['hr.payslip'].sudo().search_count([
            ('version_id', 'in', self.ids),
            ('state', 'in', ['validated', 'paid'])
        ])

    @api.ondelete(at_uninstall=False)
    def _unlink_except_valid_payslips(self):
        if self._get_valid_payslips_count() > 0:
            raise ValidationError(self.env._("You can't delete a version with validated payslips."))

    def _get_version_lookup_key(self):
        self.ensure_one()
        return (self.employee_id.id, self.contract_date_start, self.contract_date_end)

    def write(self, vals):
        if self and not self._track_disabled():
            # Force to track wage in employee form if any changes is found after version write
            self.employee_id._track_prepare({version.sudo()._get_contract_wage_field() for version in self})
        if self.env.context.get('is_simulation_offer'):
            return super().write(vals)
        if 'active' in vals and not vals['active'] and self._get_valid_payslips_count() > 0:
            raise ValidationError(self.env._("You can't archive a version with validated payslips."))
        res = super().write(vals)
        dependendant_fields = self._get_fields_that_recompute_payslip()
        if any(key in dependendant_fields for key in vals):
            for version_sudo in self.sudo():
                version_sudo._recompute_payslips(version_sudo.date_start, version_sudo.date_end or date.max)
        return res

    def copy_data(self, default=None):
        """ When copying a version, wage and final yearly cost should not both
        be kept, especially when different benefits applies. Only keep wage as
        it should not change. Final yearly cost should be recomputed based on
        the given wage."""
        vals_list = super().copy_data(default=default)
        for vals in vals_list:
            if 'wage' in vals and 'final_yearly_costs' in vals:
                vals.pop('final_yearly_costs')
        return vals_list

    def _recompute_payslips(self, date_from, date_to):
        self.ensure_one()
        all_payslips = self.env['hr.payslip'].sudo().search([
            ('version_id', '=', self.id),
            ('state', '=', 'draft'),
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
            ('company_id', '=', self.env.company.id),
        ]).filtered(lambda p: p.is_regular)
        if all_payslips:
            all_payslips.action_refresh_from_work_entries()

    def action_new_salary_attachment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payslip Adjustment'),
            'res_model': 'hr.salary.attachment',
            'view_mode': 'form',
            'view_id': self.env.ref('hr_payroll.hr_salary_attachment_view_form').id,
            'target': 'new',
            'context': {'default_employee_id': self.employee_id.id}
        }

    # YTI TODO: Probably to drop
    def _get_resource_calendar_leaves(self, start_dt, end_dt):
        # prevent leaves that are associated with a blocked payslip to be taken
        # into account, as they will be deferred lated.
        return super()._get_resource_calendar_leaves(start_dt, end_dt).filtered(lambda l: l.holiday_id.payslip_state != 'blocked')

    @api.model
    def _get_work_entry_merge_key(self, vals):
        """
        Prevent merging intervals with different category options as only the first entry option of a day would be kept after merging.
        """
        res = super()._get_work_entry_merge_key(vals)
        res += (vals.get('category_options_ids', False),)
        return res

    def _enrich_work_entry_val(self, val):
        super()._enrich_work_entry_val(val)
        # at this point leave_ids is a single hr.leave (pre-merge), so singleton access is safe
        leave = val.get('leave_ids')
        if leave and (leave.is_time_rule_trimmed or leave.source_leave_id):
            val['trimmed_duration'] = val.get('duration', 0.0)
        else:
            val['trimmed_duration'] = 0.0

    def _get_more_vals_attendance_interval(self, interval):
        """
        Append category_options_ids from the attendance slot to the work entry vals if any options are set.
        """
        vals = super()._get_more_vals_attendance_interval(interval)
        payload = interval[2]
        record = payload.record if hasattr(payload, 'record') else payload
        if record and 'category_options_ids' in record and record.category_options_ids:
            vals.append(('category_options_ids', record.category_options_ids))
        return vals

    def _get_more_vals_leave_interval(self, interval, leaves):
        """
        Append category_options_ids from the leave that fully contains the interval to the work entry vals.
        """
        result = super()._get_more_vals_leave_interval(interval, leaves)
        for leave in leaves:
            if interval[0] >= leave[0] and interval[1] <= leave[1]:
                payload = leave[2]
                record = payload.record if hasattr(payload, 'record') else payload
                if record and 'category_options_ids' in record and record.category_options_ids:
                    result.append(('category_options_ids', record.category_options_ids))
        return result

    def action_check_version_status(self):
        """ Checks if this version is the latest version and has validated payslips. """
        self.ensure_one()

        if not self.employee_id:
            return {'is_last_version': False, 'valid_payslips_count': 0}

        valid_payslips_count = self._get_valid_payslips_count()
        is_last = not self.employee_id.version_ids.filtered(lambda v: v.date_version > self.date_version)

        return {
            'is_last_version': is_last,
            'valid_payslips_count': valid_payslips_count,
        }

    def action_create_version_from_update(self, new_date_start_str, record_changes=None):
        """ Creates a new version with the applied updates starting at new_date_start_str. """
        self.ensure_one()
        record_changes = record_changes or {}
        new_start = fields.Date.from_string(new_date_start_str)

        if new_start <= self.date_start:
            raise UserError(self.env._(
                "The effective start date of the new version %(new_start)s "
                "must be after the current version's start date %(current_start)s.",
                new_start=new_start,
                current_start=self.date_start,
            ))

        if new_start > fields.Date.context_today(self):
            raise UserError(self.env._(
                "The start date of the new version (%(new_start)s) cannot be in the future. "
                "It needs to be today or before.",
                new_start=new_start,
            ))

        copy_vals = self.copy_data()[0]
        version_fields = set(self._fields.keys())
        valid_changes = {k: v for k, v in record_changes.items() if k in version_fields}

        copy_vals.update({
            'date_version': new_start,
            **valid_changes,
        })

        if self.employee_id:
            self.employee_id.create_version(copy_vals)

        return True

    def get_benefit_fields_value(self):
        if not self.env.user.has_groups('hr_payroll.group_hr_payroll_user'):
            return []
        self.ensure_one()
        salary_benefits = self.env['hr.contract.salary.benefit'].search([
            ('source', '=', 'field'),
            ('res_field_id', '!=', False),
            ('active', '=', True),
            ('country_id', '=', self.company_country_id.id),
            ('benefit_type_id.periodicity', '=', 'monthly'),
            ('structure_type_id', '=', self.structure_type_id.id),
        ])
        benefits_list = []
        for benefit in salary_benefits:
            value = self[benefit.field]
            field = self._fields.get(benefit.field)
            currency = self.currency_id.id or self.company_id.currency_id.id if field.type == 'monetary' else None
            benefits_list.append({
                'id': benefit.id,
                'name': benefit.display_name,
                'value': value,
                'currency': currency,
            })
        return benefits_list
