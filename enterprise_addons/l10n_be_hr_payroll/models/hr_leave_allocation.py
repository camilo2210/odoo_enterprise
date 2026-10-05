from collections import defaultdict
from datetime import date, timedelta
from odoo import api, models, fields

from odoo.exceptions import ValidationError

# The 3 Belgian day-based time types that also track an independent hour counter
L10N_BE_HOURS_TRACKED_WORK_ENTRY_TYPE_CODES = ['016.00', '142.24', '142.26']


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    jc_allocation_info = fields.Char(compute='_compute_jc_allocation_info')
    public_holiday_id = fields.Many2one('resource.calendar.leaves', string='Public Holiday', readonly=True)
    eligibility_warning = fields.Char(compute='_compute_eligibility_warning')
    linked_drs_ids = fields.One2many('l10n.be.drs', 'leave_allocation_id', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_hours_tracked = fields.Boolean(compute='_compute_l10n_be_hours_tracked')
    l10n_be_hours_taken = fields.Float(compute='_compute_leaves')
    l10n_be_hours_remaining = fields.Float(compute='_compute_leaves')
    l10n_be_negative_balance_warning = fields.Char(compute='_compute_leaves')

    def _get_l10n_be_hours_tracked_work_entry_types(self):
        return self.env['hr.work.entry.type'].search([
            ('country_id.code', '=', 'BE'),
            ('code', 'in', L10N_BE_HOURS_TRACKED_WORK_ENTRY_TYPE_CODES),
        ])

    def _is_l10n_be_hours_tracked_work_entry_type(self, work_entry_type):
        """Same check as _get_l10n_be_hours_tracked_work_entry_types, for a single
        already-loaded work_entry_type_id -- avoids a query when one is on hand."""
        return work_entry_type.country_id.code == 'BE' and work_entry_type.code in L10N_BE_HOURS_TRACKED_WORK_ENTRY_TYPE_CODES

    @api.model_create_multi
    def create(self, vals_list):
        tracked_types = self._get_l10n_be_hours_tracked_work_entry_types().ids
        # number_of_hours' inverse (_inverse_number_of_hours) rederives number_of_days from it,
        # clobbering an explicitly-supplied number_of_days in the same call. When both are given
        # together for one of our 3 types, both are meant to be taken at face value.
        explicit_values_by_index = {
            i: {'number_of_days': vals['number_of_days'], 'number_of_hours': vals['number_of_hours']}
            for i, vals in enumerate(vals_list)
            if 'number_of_days' in vals and 'number_of_hours' in vals and vals.get('work_entry_type_id') in tracked_types
        }
        records = super().create(vals_list)
        if explicit_values_by_index:
            self._l10n_be_force_number_of_days_and_hours({records[i]: values for i, values in explicit_values_by_index.items()})
        self._check_create_wech009()
        return records

    def write(self, vals):
        explicit_days = vals.get('number_of_days')
        explicit_hours = vals.get('number_of_hours')
        res = super().write(vals)
        if explicit_days is not None and explicit_hours is not None:
            tracked_records = self.filtered(lambda a: self._is_l10n_be_hours_tracked_work_entry_type(a.work_entry_type_id))
            if tracked_records:
                values = {'number_of_days': explicit_days, 'number_of_hours': explicit_hours}
                self._l10n_be_force_number_of_days_and_hours({record: values for record in tracked_records})
        self._check_create_wech009()
        return res

    def _l10n_be_force_number_of_days_and_hours(self, values_by_record):
        """Write number_of_days/number_of_hours directly, bypassing number_of_hours' inverse (and
        any compute), so neither silently overrides the other's just-supplied explicit value."""
        protected_fields = [self._fields['number_of_days'], self._fields['number_of_hours']]
        with self.env.protecting(protected_fields, self.browse(record.id for record in values_by_record)):
            for record, values in values_by_record.items():
                record.number_of_days = values['number_of_days']
                record.number_of_hours = values['number_of_hours']

    @api.depends('work_entry_type_id')
    def _compute_l10n_be_hours_tracked(self):
        for allocation in self:
            allocation.l10n_be_hours_tracked = self._is_l10n_be_hours_tracked_work_entry_type(allocation.work_entry_type_id)

    # Widens _compute_leaves' trigger set
    @api.depends('number_of_hours')
    def _compute_leaves(self):
        super()._compute_leaves()

    def _set_leaves_from_consumption_data(self, employee_days_per_allocation):
        super()._set_leaves_from_consumption_data(employee_days_per_allocation)

        for allocation in self:
            if not self._is_l10n_be_hours_tracked_work_entry_type(allocation.work_entry_type_id) or not allocation.employee_id:
                allocation.l10n_be_hours_taken = 0
                allocation.l10n_be_hours_remaining = 0
                allocation.l10n_be_negative_balance_warning = False
                continue

            # hours_taken/hours_remaining are always tracked in base alongside the day
            origin = allocation._origin
            virtual_leave = employee_days_per_allocation[origin.employee_id][origin.work_entry_type_id][origin]
            allocation.l10n_be_hours_taken = virtual_leave.get('hours_taken', 0)
            hours_remaining = virtual_leave.get('hours_remaining')
            allocation.l10n_be_hours_remaining = hours_remaining or 0

            if allocation.virtual_remaining_leaves < 0:
                allocation.l10n_be_negative_balance_warning = self.env._(
                    "%(employee)s has a negative day balance (%(days).2f) on %(type)s.",
                    employee=allocation.employee_id.name, days=allocation.virtual_remaining_leaves,
                    type=allocation.work_entry_type_id.name)
            elif hours_remaining is not None and hours_remaining < 0:
                allocation.l10n_be_negative_balance_warning = self.env._(
                    "%(employee)s has a negative hour balance (%(hours).2f) on %(type)s.",
                    employee=allocation.employee_id.name, hours=hours_remaining,
                    type=allocation.work_entry_type_id.name)
            else:
                allocation.l10n_be_negative_balance_warning = False

    @api.model
    def _get_l10n_be_negative_balance_warnings_batch(self, leaves):
        """Negative-balance warning messages for each leave's tracked BE allocation(s) active on
        [date_from, date_to] (used by the hr_payroll_warning_l10n_be_negative_leave_balance
        warning's evaluation_code)."""
        leaves = leaves.filtered(lambda l: l.employee_id and l.date_from)
        result = {leave.id: [] for leave in leaves}
        if not leaves:
            return result

        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', 'in', leaves.employee_id.ids),
            ('work_entry_type_id.country_id.code', '=', 'BE'),
            ('work_entry_type_id.code', 'in', L10N_BE_HOURS_TRACKED_WORK_ENTRY_TYPE_CODES),
            ('state', '=', 'validate'),
        ])
        warning_by_allocation = dict(zip(allocations.ids, allocations.mapped('l10n_be_negative_balance_warning')))
        allocations_by_employee_type = defaultdict(lambda: self.env['hr.leave.allocation'])
        for allocation in allocations:
            allocations_by_employee_type[allocation.employee_id, allocation.work_entry_type_id] |= allocation

        for leave in leaves:
            date_from = leave.date_from.date()
            date_to = leave.date_to.date() if leave.date_to else date_from
            relevant = allocations_by_employee_type[leave.employee_id, leave.work_entry_type_id].filtered(
                lambda a, date_to=date_to, date_from=date_from:
                    a.date_from <= date_to and (not a.date_to or a.date_to >= date_from)
            )
            result[leave.id] = [warning_by_allocation[a.id] for a in relevant if warning_by_allocation[a.id]]
        return result

    @api.constrains('employee_id', 'work_entry_type_id')
    def _check_youth_senior_time_off_allocation(self):
        paid_time_off_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_legal_leave')
        for allocation in self:
            if (
                allocation.work_entry_type_id
                in [
                    self.env.ref("hr_work_entry.l10n_be_work_entry_type_youth_time_off", raise_if_not_found=False),
                    self.env.ref("hr_work_entry.l10n_be_work_entry_type_senior_time_off", raise_if_not_found=False),
                ]
                and allocation.work_entry_type_id.country_id.code == 'BE'
            ):
                if paid_time_off_work_entry_type.get_work_entry_types_with_valid_allocations(
                    allocation.date_from,
                    allocation.date_to or allocation.date_from,
                    allocation.employee_id.id,
                ):
                    raise ValidationError(self.env._(
                        "You cannot allocate %(time_off_type)s for employee %(employee_name)s as they still have paid time off available.") % {
                            'time_off_type': allocation.work_entry_type_id.name,
                            'employee_name': allocation.employee_id.name,
                        })

    @api.constrains('work_entry_type_id', 'date_from', 'employee_id')
    def _check_economic_unemployment_rules(self):
        economic_unemployement_leave_allocations = self.filtered(lambda allocation: allocation.work_entry_type_id.code in ['137.00', '137.20'])
        for allocation in economic_unemployement_leave_allocations:
            version = allocation.employee_id.sudo()._get_version(date=allocation.date_from)
            if allocation.work_entry_type_id.code == '137.00':
                if not version.is_worker() or version._is_artist():
                    raise ValidationError(self.env._("Code 137.00 cannot be used for an employee who is not a worker or who is artist worker"))
            else:
                # 137.20 case
                if version.is_worker() and not version._is_artist():
                    raise ValidationError(self.env._("Code 137.20 cannot be used for a worker, unless they have an artist status"))

    def _get_max_duration(self, leave_code, jc):
        leaves_config = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('leave_durations_by_jc', raise_if_not_found=False) or {}

        duration_per_jc = leaves_config.get(leave_code)
        if not duration_per_jc:
            return False

        jc_code = jc.egov3_code if jc else None

        return duration_per_jc.get(jc_code, duration_per_jc.get(None))

    def _check_max_duration_exceeded(self):
        self.ensure_one()

        jc = self.sudo().employee_id.l10n_be_joint_committee_id
        leave_type = self.work_entry_type_id

        if not leave_type or not leave_type.code:
            return False, jc, False

        max_duration = self._get_max_duration(leave_type.code, jc)

        return bool(max_duration and self.number_of_days > max_duration), jc, max_duration

    @api.depends('employee_id', 'work_entry_type_id', 'number_of_days')
    def _compute_jc_allocation_info(self):
        self.jc_allocation_info = False
        for allocation in self:
            exceeded, jc, max_duration = allocation._check_max_duration_exceeded()

            if exceeded:
                if jc:
                    if max_duration == 1:
                        msg = self.env._("Maximum allocation in Joint Committee %(jc_name)s is %(duration)s day for this time off type.")
                    else:
                        msg = self.env._("Maximum allocation in Joint Committee %(jc_name)s is %(duration)s days for this time off type.")
                    allocation.jc_allocation_info = msg % {
                        'jc_name': jc.display_name,
                        'duration': max_duration,
                    }
                else:
                    if max_duration == 1:
                        msg = self.env._("Maximum allocation is %(duration)s day for this time off type.")
                    else:
                        msg = self.env._("Maximum allocation is %(duration)s days for this time off type.")
                    allocation.jc_allocation_info = msg % {
                        'duration': max_duration,
                    }

    @api.depends("employee_id", "work_entry_type_id", "date_from")
    def _compute_eligibility_warning(self):
        self.eligibility_warning = False
        for allocation in self:
            emp = allocation.employee_id
            if (
                allocation.work_entry_type_id == self.env.ref("hr_work_entry.l10n_be_work_entry_type_youth_time_off", raise_if_not_found=False)
                and allocation.work_entry_type_id.country_id.code == "BE"
                and emp.first_contract_date
                and (
                    allocation.date_from - emp.first_contract_date < timedelta(days=30)
                    or emp._get_age(date(allocation.date_from.year - 1, 12, 31)) >= 25
                )
            ):
                allocation.eligibility_warning = self.env._(
                    "%(employee)s is not eligible for Youth Time Off.",
                    employee=emp.name,
                )
            elif (
                allocation.work_entry_type_id == self.env.ref("hr_work_entry.l10n_be_work_entry_type_senior_time_off", raise_if_not_found=False)
                and allocation.work_entry_type_id.country_id.code == "BE"
                and emp._get_age(allocation.date_from) < 50
            ):
                allocation.eligibility_warning = self.env._(
                    "%(employee)s is not eligible for Senior Time Off.",
                    employee=emp.name,
                )

    def _check_create_wech009(self):
        youth_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_youth_time_off', raise_if_not_found=False)
        youth_holiday_risk_id = self.env.ref('l10n_be_hr_payroll.drs_risk_wech009_001').id
        senior_holiday_risk_id = self.env.ref('l10n_be_hr_payroll.drs_risk_wech009_002').id
        if not youth_type:
            return
        vals_list = []
        for allocation in self:
            if allocation.work_entry_type_id != youth_type or allocation.state != 'validate':
                continue
            # Right to youth holidays is defined based on the age at the end of the year
            # at which the employee takes the holidays
            age = allocation.employee_id._get_age(allocation.date_from.replace(month=12, day=31))
            if age < 25:
                risk_id = youth_holiday_risk_id
            elif age >= 50:
                risk_id = senior_holiday_risk_id
            else:
                continue
            linked_wech009 = allocation.linked_drs_ids.filtered(lambda drs: drs.identification == 'WECH009' and drs.code == '001')
            if not linked_wech009:
                vals_list.append({
                    'is_automatically_created': True,
                    'employee_id': allocation.employee_id.id,
                    'sector': 'unemployment',
                    'risk_id': risk_id,
                    'leave_allocation_id': allocation.id,
                })
        self.env['l10n.be.drs'].create(vals_list)

    def action_show_related_drs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('l10n_be_hr_payroll.action_drs')
        action['domain'] = [('id', 'in', self.linked_drs_ids.ids)]
        action['context'] = {'default_employee_id': self.employee_id.id}
        if len(self.linked_drs_ids) == 1:
            action.update({
                "views": [[False, "form"]],
                "res_id": self.linked_drs_ids.id,
            })
        return action
