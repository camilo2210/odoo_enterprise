# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from collections import defaultdict
from datetime import date
import json
import logging

from dateutil.relativedelta import relativedelta, MO
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.fields import Domain
from odoo.tools.safe_eval import datetime as safe_eval_datetime, wrap_module
from odoo.tools.safe_eval import dateutil as safe_eval_dateutil
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import html_translate
from odoo.tools import date_utils, float_compare, html2plaintext

_logger = logging.getLogger(__name__)


class HrPayrollWarning(models.Model):
    _name = 'hr.payroll.warning'
    _description = 'Payroll Warning'
    _order = 'sequence, name'

    def _get_model_id_domain(self):
        allowed_models = self._get_allowed_models()
        return [('model', 'in', allowed_models)]

    def _get_allowed_models(self):
        return ['hr.employee', 'hr.version', 'hr.payslip', 'hr.leave']

    name = fields.Char(required=True, translate=True)
    description = fields.Char(translate=True)
    active = fields.Boolean(default=True)
    snooze_date = fields.Date(string="Snoozed Until")
    warning_type = fields.Selection(selection=[
        ('domain', "Domain"),
        ('python', "Python Code")
    ], string="Type", default='python', required=True)
    is_in_contract = fields.Boolean("Running Contracts", help="Limits the warning to employees with a running contract")
    can_be_in_contract = fields.Boolean(compute='_compute_can_be_in_contract', store=False)
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        ondelete='cascade',
        domain=_get_model_id_domain
    )
    model_name = fields.Char(string="Model Name", related='model_id.model', store=True)
    email_visibility_type_id = fields.Selection(string="Email To", required=True,
        selection=[('assistant', "Assistant"), ('officer', "Officer"), ('admin', "Admin"), ('employee', "Employee"), ('employee_manager', "Employee's Manager")],
        default='assistant'
    )
    visible_to = fields.Selection(string="Visible To", selection=[('assistant', 'Assistant'), ('officer', 'Officer'), ('admin', 'Admin')], required=True, default='assistant')
    warning_domain = fields.Char("Warning Domain")
    block_payslips = fields.Boolean("Block Payslips",
        help="Blocks the payslip while validating, if warning")
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.company.country_id,
        domain=lambda self: [('id', 'in', self.env.companies.country_id.ids)])
    warning_color_class = fields.Selection(selection=[
        ('warning', "Warning"),
        ('danger', "Danger"),
        ('primary', "Primary"),
        ('secondary', "Secondary"),
        ('info', "Info"),
        ('success', "Success"),
        ('dark', "Dark"),
        ('light', "Light"),
    ], default='info', string="Color Class", required=True, help="Type of the warning")
    evaluation_code = fields.Text(string='Python Code')
    sequence = fields.Integer(default=10)
    warning_offset_days = fields.Integer(string="Warning Offset (Days)",
        help="""Number of days used to compute the warning date based on the selected 'Closing On' rule.
        - For contract start/end: the warning will trigger this many days before the contract start or end dates.
        - For next payslip: the offset is applied before or after the payrun closing date.
    """)
    closing_on = fields.Selection(selection=[
        ('today', "Today"),
        ('next_payslip', "Next Payslip"),
        ('contract_start', "Contract Start"),
        ('contract_end', "Contract End"),
        ('end_of_month', "End of the Month"),
        ('end_of_quarter', "End of the Quarter"),
        ('end_of_year', "End of the Year"),
        ('payroll_start_date', "Payroll Start Date"),
    ], default="next_payslip", required=True, help="""
        Defines the reference date used to compute when the warning becomes due.
        - Today: Uses the current date as the reference point, so the warning stays a fixed distance away.
        - Next Payslip: Uses the payrun closing date as the reference point.
        - Contract Start / Contract End: Uses the employee's contract start or end date as the reference point.
        - End of Month / Quarter / Year: Uses the end of the current month / quarter / year as the reference point.
        - Payroll Start Date: Uses the payroll start date as the reference point.
        The warning date is then calculated by applying the Offset (Days) to this reference.
    """)
    email_alert_days = fields.Integer(string="Email Alert", help="After these many days from the warning date, an alert email will be sent.")
    email_message = fields.Html("Email Message", translate=html_translate, help="This message body will be sent as an email.")
    is_email_message_empty = fields.Boolean(compute='_compute_is_email_empty', store=True)
    button_name = fields.Char("Button Name", default="Review Records", translate=True, help="The name that will be shown as button on the warning card")
    button_action = fields.Many2one('ir.actions.actions', string="Action")
    display_on_dashboard = fields.Boolean(default=True, string="Dashboard")
    display_on_model = fields.Boolean(string="Record", help="Only Employee, Version, Timeoff request and Payslip are supported models.")

    @api.constrains('display_on_dashboard', 'display_on_model')
    def _check_display_on_destination(self):
        for warning in self:
            if not warning.display_on_dashboard and not warning.display_on_model:
                raise ValidationError(_("A payroll warning must be displayed on at least one target (Dashboard and/or Model View and/or DMFA)."))

    def _models_connected_to_contract(self):
        return {
            "hr.employee": ("contract_date_start", "contract_date_end"),
            "hr.version":  ("employee_id.contract_date_start", "employee_id.contract_date_end"),
            "fleet.vehicle": ("driver_id.employee_ids.contract_date_start", "driver_id.employee_ids.contract_date_end"),
        }

    @api.depends('warning_type', 'model_id')
    def _compute_can_be_in_contract(self):
        model_with_contract = self._models_connected_to_contract()
        for payroll_warning in self:
            payroll_warning.can_be_in_contract = bool(model_with_contract.get(payroll_warning.model_name, False))

    @api.depends('email_message')
    def _compute_is_email_empty(self):
        for record in self:
            content = html2plaintext(record.email_message or '').strip()
            record.is_email_message_empty = not bool(content)

    @api.constrains('evaluation_code')
    def _check_dates(self):
        for warning in self:
            if warning.evaluation_code and 'self.env._' in warning.evaluation_code:
                _logger.warning("self.env._ won't export the source term in .pot file, define in explicitely using '_get_payroll_translation'")

    def action_snooze(self):
        self.snooze_date = fields.Date.today() + relativedelta(days=25)

    def _get_schedule_closing_date(self, schedule, closing_date):
        """Return the schedule's pay run closing date.

        :param str schedule: structure type schedule.
        :param date closing_date: monthly closing date.
        :rtype date | None

        Non-monthly schedules use hardcoded reference dates:
        - daily: today
        - weekly: every Monday
        - bi-weekly: every other Monday (starting from the 2nd Monday of the year)
        - semi-monthly: 1st or 15th
        - bi-monthly: same day as monthly, but every other month
        - quarterly: end dates of all the quarters (31st March, 30th June, 31st Oct, and 31st Dec)
        - half-yearly: 30th June and 31st December
        - yearly: 31st December
        """
        if not closing_date:
            return None

        today = fields.Date.context_today(self)

        def _next_monday(from_date):
            return from_date + relativedelta(weekday=0)

        def _next_biweekly_monday(from_date):
            second_monday_of_the_year = date(from_date.year, 1, 1) + relativedelta(weekday=MO, weeks=1)
            if from_date < second_monday_of_the_year:
                return second_monday_of_the_year
            weeks_since = (from_date - second_monday_of_the_year).days // 7
            if from_date.weekday() == 0 and weeks_since % 2 == 0:
                return from_date
            week_offset = 2 if weeks_since % 2 == 0 else 1
            return second_monday_of_the_year + relativedelta(weeks=weeks_since + week_offset)

        def _semi_monthly_date(from_date):
            if from_date.day == 1:
                return from_date.replace(day=1)
            if from_date.day <= 15:
                return from_date.replace(day=15)
            return from_date + relativedelta(months=1, day=1)

        def _current_quarter_end(date):
            quarter = (date.month - 1) // 3 + 1
            end_month = quarter * 3
            return date + relativedelta(months=1, days=-1, month=end_month, day=1)

        match schedule:
            case 'daily':
                closing_date = today
            case 'weekly':
                closing_date = _next_monday(today)
            case 'bi-weekly':
                closing_date = _next_biweekly_monday(today)
            case 'semi-monthly':
                closing_date = _semi_monthly_date(today)
            case 'bi-monthly':
                closing_date += relativedelta(
                    months=(closing_date.month - self.env.company.first_payrun_date.month) % 2
                )
            case 'quarterly':
                closing_date = _current_quarter_end(today)
            case 'semi-annually':
                day, month = (30, 6) if today.month <= 6 else (31, 12)
                closing_date = today.replace(month=month, day=day)
            case 'annually':
                closing_date = today + relativedelta(year=today.year + 1, month=1, day=1, days=-1)

        return closing_date

    def _get_schedule_pay(self, record):
        if 'structure_type_id' in record and record.structure_type_id:
            return record.structure_type_id.default_schedule_pay
        if 'employee_id' in record and record.employee_id.structure_type_id:
            return record.employee_id.structure_type_id.default_schedule_pay
        return 'monthly'

    def _get_warning_date(self, warning_record, closing_date):
        """Return the computed warning date.

        :param recordset warning_record: record associated with the warning.
        :param date closing_date: structure type closing date.
        :rtype date | None
        """
        self.ensure_one()

        schedule = self._get_schedule_pay(warning_record)
        closing_date = self._get_schedule_closing_date(schedule, closing_date) if schedule != 'monthly' else closing_date

        if not closing_date:
            return None

        warning_date = None

        if self.closing_on in ('contract_start', 'contract_end'):
            contract_date_start_field, contract_date_end_field = self._models_connected_to_contract().get(
                self.model_name, False,
            )
            if self.closing_on == 'contract_start' and contract_date_start_field:
                contract_date_start = min(warning_record.mapped(contract_date_start_field))
                if contract_date_start:
                    warning_date = contract_date_start + relativedelta(days=self.warning_offset_days)
            elif self.closing_on == 'contract_end' and contract_date_end_field:
                contract_date_end = min(warning_record.mapped(contract_date_end_field))
                if contract_date_end:
                    warning_date = contract_date_end + relativedelta(days=self.warning_offset_days)

        elif self.closing_on == 'today':
            warning_date = fields.Date.context_today(self) + relativedelta(days=self.warning_offset_days)

        elif self.closing_on == 'next_payslip':
            warning_date = closing_date + relativedelta(days=self.warning_offset_days)

        elif self.closing_on == 'end_of_month':
            end_of_current_month = date.today() + relativedelta(day=31)
            warning_date = end_of_current_month + relativedelta(days=self.warning_offset_days)

        elif self.closing_on == 'end_of_quarter':
            end_of_current_quarter = date_utils.get_quarter(date.today())[1]
            warning_date = end_of_current_quarter + relativedelta(days=self.warning_offset_days)

        elif self.closing_on == 'end_of_year':
            end_of_current_year = date.today().replace(month=12, day=31)
            warning_date = end_of_current_year + relativedelta(days=self.warning_offset_days)

        elif self.closing_on == 'payroll_start_date':
            payroll_start_date = self.env.company.first_payrun_date or date.today()
            warning_date = payroll_start_date + relativedelta(days=self.warning_offset_days)

        return warning_date

    def _filter_warning_records_by_contract_period(self, warning_records, period_start, period_end):
        """Return the filtered records with duration applied.

        :param recordset warning_records: records associated with the warning.
        :param date period_start: last month's closing date + 1 day.
        :param date period_end: this month's closing date.
        :rtype recordset
        :return: records with applied duration (if applicable), else all records.
        """
        contract_date_start_field, contract_date_end_field = self._models_connected_to_contract().get(
            warning_records._name,
            False,
        )
        if contract_date_start_field:
            warning_records = warning_records.filtered_domain(
                [
                    (contract_date_start_field, "!=", False),
                    (contract_date_start_field, "<", period_end),
                    "|",
                    (contract_date_end_field, "!=", False),
                    (contract_date_end_field, ">", period_start),
                ],
            )
        return warning_records

    def _group_records_by_schedule(self, warning_records):
        grouped_ids = defaultdict(list)
        for record in warning_records:
            schedule = self._get_schedule_pay(record)
            grouped_ids[schedule].append(record.id)
        return {
            schedule: self.env[warning_records._name].browse(ids)
            for schedule, ids in grouped_ids.items()
        }

    def _group_by_warning_and_date(self, warning, records, closing_date):
        grouped_ids = defaultdict(list)
        for record in records:
            warning_date = warning._get_warning_date(record, closing_date)
            if not warning_date:
                warning_date = fields.Date.context_today(self)
            key = (warning.id, warning_date)
            grouped_ids[key].append(record.id)
        return {
            key: self.env[records._name].browse(ids)
            for key, ids in grouped_ids.items()
        }

    def _dashboard_default_action(self, name, records, additional_context=None):
        self.ensure_one()
        if not additional_context:
            additional_context = {}
        if len(records) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': name,
                'res_model': records._name,
                'res_id': records.id,
                'context': {**self.env.context, **additional_context},
                'views': [[False, 'form']],
                'view_mode': 'form',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': records._name,
            'context': {**self.env.context, **additional_context},
            'domain': [('id', 'in', records.ids)],
            'views': [[False, 'list'], [False, 'kanban'], [False, 'form']],
            'view_mode': 'list,kanban,form',
        }

    def _dashboard_company_action(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'res.company',
            'res_id': self.env.company.id,
        }

    def _get_next_payrun(self, company, date_start, date_end, employee_types=None):
        domain = [
            ('company_id', '=', company.id),
            ('date_start', '>=', date_start),
            ('date_end', '<=', date_end),
        ]
        if employee_types:
            domain.append(('employee_type_ids', 'in', employee_types.ids))
        return self.env["hr.payslip.run"].search(domain)

    def _get_monthly_payroll_next_closing_date(self, payroll_closing_date):
        if not payroll_closing_date:
            return None
        today = fields.Date.context_today(self)
        payrun_closing_day = int(payroll_closing_date)
        month_offset = 1 if payrun_closing_day <= 9 else 0

        closing_date = today + relativedelta(months=month_offset, day=payrun_closing_day)
        if today > closing_date:
            closing_date += relativedelta(months=1, day=payrun_closing_day)
        return closing_date

    def _get_effective_warning_domain(self, company, *, block_payslips=False, with_email_message=False):
        effective_domain = Domain.AND([
            ['|', ('country_id', '=', company.country_id.id), ('country_id', '=', False)],
            ['|', ('snooze_date', '=', False), ('snooze_date', '<', 'today')]
        ])
        if block_payslips:
            effective_domain &= Domain('block_payslips', '=', True)
        if with_email_message:
            effective_domain &= Domain('email_message', '!=', False)
        return effective_domain

    def _get_applicable_payroll_warnings(self, company, **kwargs):
        """Returns the structured list of warnings

        Eager version of :meth:`_iter_applicable_payroll_warnings`, see it for
        the accepted arguments and the shape of the returned dicts.

        :rtype List[dict]
        """
        return list(self._iter_applicable_payroll_warnings(company, **kwargs))

    def _iter_applicable_payroll_warnings(self, company, *, block_payslips=False, with_email_message=False, include_model_warnings=False):
        """Yields the structured warnings, one at a time

        :param res.company company: to get provided company specific warnings
        :param bool block_payslips: to filter warnings that block payslip enabled.
        :param bool with_email_message: to filter warnings that have not null email_message.
        :rtype Iterator[dict]

        :returns: An iterator of structured warnings, containing all the information required
            to display the warning or dashboard or to send email if warning is overdue.
            Yielding lazily lets the dashboard stream each card as soon as it is ready.
        """
        closing_date = company._get_monthly_payroll_next_closing_date()

        if not self:
            effective_domain = self._get_effective_warning_domain(
                company,
                block_payslips=block_payslips,
                with_email_message=with_email_message,
            )
            warnings = self.search(effective_domain)
        else:
            warnings = self

        for warning in warnings:
            if not include_model_warnings and not warning.display_on_dashboard:
                continue
            context = {'warning_action': False}
            additional_context = {}
            if warning.warning_type == 'python':
                context.update({
                    'company': company,
                    'closing_date': closing_date,
                    'warning_multi_results': False,
                    'Domain': Domain,
                    'literal_eval': literal_eval,
                })
                warning_records, _, additional_context, context = warning._get_warning_python_records(context)

                if multi_results := context.get('warning_multi_results'):
                    # In the case of hr_payroll_warning_payrun_employee_type
                    # we return the overridden values directly in the result dictionary
                    # to display different cards on the dashboard with only one record
                    # in the hr.payroll.warning model.
                    for entry in multi_results:
                        yield {
                            'warning': warning,
                            'warning_id': warning.id,
                            'warning_name': entry['name'],
                            'warning_description': entry.get('description', ''),
                            'warning_color_class': warning.warning_color_class,
                            'warning_button_name': entry['button_name'],
                            'count': -1,
                            'structure_type_schedule': entry.get('schedule', 'monthly'),
                            'records': entry.get('records', []),
                            'warning_date': entry['warning_date'],
                            'button_action': entry['action'],
                        }
                    continue
            else:
                warning_records = warning._get_warning_domain_records(self.env.companies)

            if isinstance(closing_date, date) and warning.warning_type == 'domain' and warning.is_in_contract:
                period_start = closing_date + relativedelta(months=-1, days=1)  # last_closing_date + 1
                warning_records = self._filter_warning_records_by_contract_period(warning_records, period_start, closing_date)
                context['warning_count'] = len(warning_records)

            if not warning_records:
                continue

            records_by_schedule = self._group_records_by_schedule(warning_records)

            for schedule, records in records_by_schedule.items():
                warning_date_and_records = self._group_by_warning_and_date(warning, records, closing_date)
                for (warning_id, warning_date), grouped_records in warning_date_and_records.items():
                    if context_action := context.get('warning_action'):  # to get action from evaluation_code if available.
                        button_action = context_action
                        button_action.update({
                            'domain': [('id', 'in', grouped_records.ids)],
                        })
                    elif warning.button_action:
                        button_action = warning.button_action._get_action_dict()
                        if button_action['type'] == 'ir.actions.act_window':
                            button_action = self.env['ir.actions.act_window'].browse(button_action['id'])._get_action_dict()
                        if button_action.get('res_model', False) == grouped_records._name:
                            button_action.update({
                                'domain': [('id', 'in', grouped_records.ids)],
                            })
                    else:
                        button_action = warning._dashboard_default_action(warning.name, grouped_records, additional_context)

                    ctx = button_action.get('context', {})
                    if isinstance(ctx, str):
                        ctx = literal_eval(ctx)

                    button_action['context'] = dict(ctx, **additional_context)

                    yield {
                        'warning': warning,
                        'warning_id': warning.id,
                        'warning_name': context.get('warning_title', False) or warning.name,
                        'warning_description': context.get('warning_description', False) or warning.description,
                        'warning_color_class': warning.warning_color_class,
                        'warning_button_name': context.get('warning_button', False) or warning.button_name,
                        'structure_type_schedule': schedule,
                        'records': grouped_records,
                        'warning_date': context.get('warning_deadline', False) or warning_date,
                        'count': context.get('warning_count', -1),
                        'button_action': button_action,
                    }

    def _get_warning_domain_records(self, companies, records_to_check=None):
        try:
            warning_model = self.env[self.sudo().model_id.model]
            warning_domain = literal_eval(self.warning_domain or '[]')
            if 'company_id' in warning_model:
                if self.sudo().country_id:
                    warning_domain.extend([
                        ('company_id.partner_id.country_id', '=', self.sudo().country_id.id),
                    ])
                warning_domain.extend([
                    '|',
                        ('company_id', '=', False),
                        ('company_id', 'in', companies.ids),
                ])
            if self.sudo().model_id.model == 'res.company':
                if self.sudo().country_id:
                    warning_domain.extend([
                        ('partner_id.country_id', '=', self.sudo().country_id.id),
                    ])

            if warning_model._name == 'res.company':
                return companies.filtered_domain(warning_domain)
            if records_to_check is not None and records_to_check._name == warning_model._name:
                return records_to_check.filtered_domain(warning_domain)
            return warning_model.search(warning_domain)
        except Exception as e:  # noqa: BLE001
            raise UserError(
                self.env._(
                    "Wrong warning domain defined for:\n- Warning: %(warning)s\n- Error: %(error)s",
                    warning=self.name,
                    error=e,
                ),
            )

    def _get_warning_python_records(self, localdict):
        self.ensure_one()
        localdict.update({
            'date': safe_eval_datetime.date,
            'datetime': safe_eval_datetime.datetime,
            'relativedelta': safe_eval_dateutil.relativedelta.relativedelta,
            'dateutil': safe_eval_dateutil,
            'float_compare': float_compare,
            'self': self,
            'warning_count': -1,
            'warning_title': False,
            'warning_description': False,
            'warning_deadline': False,
            'warning_button': False,
            'warning_records': self.env['base'],
            'warning_details': False,
            'warning_action': False,
            'additional_context': {},
            'defaultdict': defaultdict,
            '_get_payroll_translation': self._get_payroll_translation,
            'json': wrap_module(json, ['dumps', 'loads']),
        })

        if self.model_id:
            # The caller may hand over the records themselves, so that unsaved ones are also checked.
            localdict.setdefault('records', self.env[self.model_name].browse(localdict.get('active_ids', [])))
            localdict['model'] = self.env[self.model_name]

        try:
            safe_eval(self.evaluation_code, localdict, mode='exec')
        except Exception as e:  # noqa: BLE001
            raise UserError(
                self.env._(
                    "Wrong warning computation code defined for:\n- Warning: %(warning)s\n- Error: %(error)s",
                    warning=self.name,
                    error=e,
                )
            )
        return localdict.get('warning_records'), localdict.get('warning_details'), localdict.get('additional_context'), localdict

    def _get_warning_issue(self):
        return {
            'message': self.description or self.name,
            'level': self.warning_color_class if self.warning_color_class in ['warning', 'danger'] else 'warning',
        }

    @api.model
    def get_payroll_dashboard_data(self):
        """Return lightweight dashboard data for progressive loading on the client."""
        company = self.env.company
        warnings = self.search(self._get_effective_warning_domain(company))
        relevant_structure_types_schedules = set(
            self.env['hr.payroll.structure.type']
                .search([('country_id', '=', company.country_id.id)])
                .mapped('default_schedule_pay')
        )
        company_closing_date = company._get_monthly_payroll_next_closing_date()
        closing_dates_data = []
        for schedule in relevant_structure_types_schedules:
            closing_date = self._get_schedule_closing_date(schedule, company_closing_date)
            if closing_date:
                closing_dates_data.append({
                    'schedule': schedule,
                    'closing_date': closing_date,
                    'label': self.env._("%s Payrun", schedule.title() if schedule else ''),
                })
        closing_dates_data.sort(key=lambda c: c['closing_date'])

        return {
            'closing_dates_data': closing_dates_data,
            'mandatory_config_id': self.env.ref('hr_payroll.hr_payroll_warning_set_schedule').id,
            'warning_ids': warnings.ids,
        }

    @api.model
    def get_payroll_dashboard_warning_cards(self, warning_ids, *, block_payslips=False, with_email_message=False, include_model_warnings=False):
        """Return the serialized dashboard warning cards for the provided warning ids."""
        company = self.env.company
        warnings = self.browse(warning_ids)
        return [
            self._serialize_card(warning_data)
            for warning_data in warnings._get_applicable_payroll_warnings(
                company,
                block_payslips=block_payslips,
                with_email_message=with_email_message,
                include_model_warnings=include_model_warnings,
            )
        ]

    def _serialize_card(self, warning_data):
        warning_id = warning_data['warning_id']
        schedule = warning_data['structure_type_schedule']
        records = warning_data['records']
        return {
            'id': warning_id or False,
            'key': f"{schedule}_{warning_id}",
            'name': warning_data['warning_name'],
            'description': warning_data['warning_description'] or '',
            'structure_type_suffix': (
                self.env._("%s Scheduled Pay", schedule.title())
                if schedule and schedule != 'monthly' else ''
            ),
            'warning_records': records,
            'count': warning_data['count'] if warning_data['count'] != -1 else len(records),
            'color_class': warning_data['warning_color_class'],
            'warning_date': warning_data['warning_date'],
            'button_name': warning_data['warning_button_name'],
            'button_action': warning_data['button_action'],
        }

    def _serialize_error_card(self, error_data):
        return {
            'id': self.id,
            'key': f"error_{self.id}",
            'name': self.name,
            'description': self.env._("This warning could not be computed."),
            'color_class': 'danger',
            'is_error': True,
            'warning_date': fields.Date.context_today(self).isoformat(),
            'button_name': self.env._("See details"),
            'button_action': {
                'type': 'ir.actions.client',
                'tag': 'display_exception',
                'params': {
                    'message': error_data['message'],
                    'data': error_data,
                },
            },
        }

    @api.model
    def _cron_payroll_warning_email_alert(self):
        """Send email alerts for overdue payroll warnings.

        The process:
        - Fetch all dashboard warnings (company-wise) with a non-null email_message.
        - Filter warnings whose alert date matches today, based on email_alert_days.
        - Determine recipients from the Payroll User group.
        - For each matched warning, prepare individual email messages and send.
        """
        companies = self.env['res.company'].search([
            ('first_payrun_date', '!=', False),
            ('payroll_closing_date', '!=', False),
        ])
        if not companies:
            return

        today = fields.Date.context_today(self)
        warning_mails = []

        for company in companies:
            warnings_data = self._get_applicable_payroll_warnings(company, with_email_message=True)
            missed_warnings_data = [
                warning_data for warning_data in warnings_data
                if warning_data['warning'].closing_on != 'today' and (today - warning_data['warning_date']).days == warning_data['warning'].email_alert_days
            ]
            if not missed_warnings_data:
                continue

            payroll_user_group = self.env.ref('hr_payroll.group_hr_payroll_user')
            payroll_officer_group = self.env.ref('hr_payroll.group_hr_payroll_officer')
            payroll_manager_group = self.env.ref('hr_payroll.group_hr_payroll_manager')
            for warning_data in missed_warnings_data:
                warning = warning_data['warning']
                if warning.email_visibility_type_id == 'employee':
                    warning_domain = literal_eval(warning.warning_domain or '[]')
                    employees = self.env['hr.employee'].search(warning_domain)
                    recipients_emails = ','.join(employees.filtered('work_email').mapped('work_email'))
                elif warning.email_visibility_type_id == 'employee_manager':
                    warning_domain = literal_eval(warning.warning_domain or '[]')
                    employees_managers = self.env['hr.employee'].search(warning_domain).mapped("parent_id")
                    recipients_emails = ','.join(employees_managers.filtered('work_email').mapped('work_email'))
                else:
                    payroll_group = payroll_user_group
                    if warning.email_visibility_type_id == 'officer':
                        payroll_group = payroll_officer_group
                    elif warning.email_visibility_type_id == 'admin':
                        payroll_group = payroll_manager_group

                    recipients = payroll_group.all_implied_by_ids.user_ids.filtered_domain([('company_ids', 'in', company.id)])
                    recipients_emails = ','.join(recipients.filtered('email').mapped('email'))
                if not recipients_emails:
                    continue

                warning_mails.append({
                    'subject': self.env._("Warning Alert: %s", warning.name),
                    'body_html': Markup(warning.email_message),
                    'email_to': recipients_emails,
                })

        if warning_mails:
            self.env['mail.mail'].sudo().create(warning_mails).send()

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "A payslip adjustment has been created":
            return self.env._("A payslip adjustment has been created")
        if text == "Adjustment":
            return self.env._("Adjustment")
        if text == "Bank Accounts":
            return self.env._("Bank Accounts")
        if text == "Batch":
            return self.env._("Batch")
        if text == "Company record is out of date.":
            return self.env._("Company record is out of date.")
        if text == "Contract":
            return self.env._("Contract")
        if text == "Continue":
            return self.env._("Continue")
        if text == "Correct Payslip":
            return self.env._("Correct Payslip")
        if text == "Payrun: %(period)s":
            return self.env._("Payrun: %(period)s", **kwargs)
        if text == "Current Payrun: %(next_payrun)s":
            return self.env._("Current Payrun: %(next_payrun)s", **kwargs)
        if text == "Current Payrun: %(employee_type)s - %(next_payrun)s":
            return self.env._("Current Payrun: %(employee_type)s - %(next_payrun)s", **kwargs)
        if text == "Duplicate payslips":
            return self.env._("Duplicate payslips")
        if text == "Duplicate Payslips":
            return self.env._("Duplicate Payslips")
        if text == "Duplicates":
            return self.env._("Duplicates")
        if text == "Employee":
            return self.env._("Employee")
        if text == "Employee record is out of date.":
            return self.env._("Employee record is out of date.")
        if text == "Employee's version has changed.":
            return self.env._("Employee's version has changed.")
        if text == "A time off has been modified.":
            return self.env._("A time off has been modified.")
        if text == "A time off overlapping this payslip period is not validated.":
            return self.env._("A time off overlapping this payslip period is not validated.")
        if text == "Update Payslip":
            return self.env._("Update Payslip")
        if text == "Multiple Pay Run overlap the same period":
            return self.env._("Multiple Pay Run overlap the same period")
        if text == "Multiple Pay Run for %(employee_type)s overlap the same period (%(date_range)s)":
            return self.env._("Multiple Pay Run for %(employee_type)s overlap the same period (%(date_range)s)", **kwargs)
        if text == "Never miss a deadline!":
            return self.env._("Never miss a deadline!")
        if text == "Review employees and time offs to generate payslips.":
            return self.env._("Review employees and time offs to generate payslips.")
        if text == "No bank account":
            return self.env._("No bank account")
        if text == "No running contract":
            return self.env._("No running contract")
        if text == "Open Pay Runs":
            return self.env._("Open Pay Runs")
        if text == "Overlapping time off modified.":
            return self.env._("Overlapping time off modified.")
        if text == "Pay run":
            return self.env._("Pay run")
        if text == "Payslip for the month is already validated.":
            return self.env._("Payslip for the month is already validated.")
        if text == "Related payslip adjustment has been closed since the creation of this payslip":
            return self.env._("Related payslip adjustment has been closed since the creation of this payslip")
        if text == "Related payslip adjustment has been closed":
            return self.env._("Related payslip adjustment has been closed")
        if text == "Payslip for the month is already validated.":
            return self.env._("Payslip for the month is already validated.")
        if text == "Related salary adjustment has been closed":
            return self.env._("Related salary adjustment has been closed")
        if text == "Review":
            return self.env._("Review")
        if text == "Review employee to validate payslip.":
            return self.env._("Review employee to validate payslip.")
        if text == "Salary adjustment closed.":
            return self.env._("Salary adjustment closed.")
        if text == "Salary adjustment created.":
            return self.env._("Salary adjustment created.")
        if text == "Start Pay Run":
            return self.env._("Start Pay Run")
        if text == "Start Pay run - %(date_range)s (%(employee_type)s)":
            return self.env._("Start Pay run - %(date_range)s (%(employee_type)s)", **kwargs)
        if text == "State of the payrun: %(state)s":
            return self.env._("State of the payrun: %(state)s", **kwargs)
        if text == "The company has been updated.":
            return self.env._("The company has been updated.")
        if text == "The employee has been updated.":
            return self.env._("The employee has been updated.")
        if text == "Untrusted bank accounts":
            return self.env._("Untrusted bank accounts")
        if text == "Wrong company":
            return self.env._("Wrong company")
        if text == "The company has been updated.":
            return self.env._("The company has been updated.")
        if text == "The company's version has changed.":
            return self.env._("The company's version has changed.")
        if text == "Time Offs":
            return self.env._("Time Offs")
        _logger.warning('Translation source term not explicitely defined (It could remain untranslated) for:\n%s', text)
        if kwargs:
            return text.format(**kwargs)
        return text
