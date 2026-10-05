from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date


class HrPayrollSalaryIncrease(models.TransientModel):
    _inherit = 'hr.payroll.salary.increase'

    type = fields.Selection(string="Type", selection=[('manual', 'Manual'), ('legal', 'Legal Indexation')], default='manual', required=True)
    year = fields.Char(string="Year", required=True, default=lambda self: str(fields.Date.context_today(self).year))
    rate = fields.Float(string="Rate (%)", required=True, compute="_compute_rate")
    legal_indexation_available = fields.Boolean(
        string="Legal Indexation Available",
        compute="_compute_legal_indexation_available",
    )
    legal_indexation_warning = fields.Char(string="Legal Indexation Warning", compute="_compute_legal_indexation_available")
    country_code = fields.Char(related='company_id.country_id.code', readonly=True)

    @api.depends('employee_ids', 'year')
    def _compute_legal_indexation_available(self):
        for record in self:
            if not record.employee_ids or not record.year:
                record.legal_indexation_available = False
                record.legal_indexation_warning = self.env._("Please select employees and year to check legal indexation availability.")
                continue
            if any(not employee.l10n_be_egov3_code for employee in record.employee_ids):
                record.legal_indexation_available = False
                record.legal_indexation_warning = self.env._("The following employees do not have a Joint Committee assigned: %s", ", ".join(employee.name for employee in record.employee_ids if not employee.l10n_be_egov3_code))
                continue
            egov3_codes = set(filter(None, record.employee_ids.mapped('l10n_be_egov3_code')))
            if len(egov3_codes) > 1:
                record.legal_indexation_available = False
                record.legal_indexation_warning = self.env._("The following employees are assigned to different Joint Committees: %s", ", ".join(record.employee_ids.mapped('name')))
                continue
            egov3_code = next(iter(egov3_codes))
            rule_parameter = self.env["hr.rule.parameter"]._get_parameter_from_code(
                "l10n_be_legal_index",
                date=date(int(record.year), 1, 1),
                raise_if_not_found=False,
            )
            record.legal_indexation_available = bool(
                rule_parameter and rule_parameter.get(egov3_code),
            )
            record.legal_indexation_warning = (
                self.env._(
                    "The selected employees do not belong to a Joint Committee eligible for legal indexation: %s",
                    ", ".join(record.employee_ids.mapped("name")),
                )
                if not record.legal_indexation_available
                else ""
            )

    @api.onchange('employee_ids', 'year')
    def _onchange_legal_indexation_availability(self):
        if not self.legal_indexation_available:
            self.type = 'manual'

    @api.onchange('type', 'year')
    def _onchange_type_year(self):
        if self.type == 'legal' and self.year:
            self.increase_date = date(int(self.year), 1, 1)

    @api.depends('type', 'year')
    def _compute_rate(self):
        rule_parameter = self.env["hr.rule.parameter"]._get_parameter_from_code(
            "l10n_be_legal_index", date=date(int(self.year), 1, 1), raise_if_not_found=False,
        )
        for record in self:
            if record.type == 'legal':
                if not rule_parameter or not rule_parameter.get(record.employee_ids[0].l10n_be_egov3_code):
                    record.rate = 0.0
                    continue
                record.rate = rule_parameter.get(record.employee_ids[0].l10n_be_egov3_code)[0]
                continue
            record.rate = 0.0

    def _indexation_issues_check(self):
        if self.type == 'manual':
            return super()._indexation_issues_check()
        if len(set(self.employee_ids.mapped('l10n_be_egov3_code'))) > 1:
            raise UserError(self.env._("All selected employees must have the same joint committee for legal indexation."))

    def _index_wage(self, employee, base_version):
        self.ensure_one()
        wage_field = base_version._get_contract_wage_field()
        if self.type == 'manual':
            super()._index_wage(employee, base_version)
            return

        rule_parameters = self.env["hr.rule.parameter"]._get_parameter_from_code(
            "l10n_be_legal_index", date=date(int(self.year), 1, 1), raise_if_not_found=False,
        )
        if not rule_parameters or not rule_parameters.get(base_version.l10n_be_egov3_code):
            return
        rate, cap = rule_parameters.get(base_version.l10n_be_egov3_code)
        # Convert the wage to monthly equivalent salary (for hourly/daily paid employees  and part-timers)
        reference_wage = base_version._l10n_be_get_monthly_wage(int(self.year))
        capped_amount = max(reference_wage - (cap or reference_wage), 0)
        new_reference_wage = reference_wage + self._compute_increase_amount(reference_wage, cap, rate)
        new_wage = base_version._get_wage_from_reference_salary(int(self.year), new_reference_wage)

        if base_version.date_version != self.increase_date:
            employee.create_version({
                'date_version': self.increase_date,
                wage_field: new_wage,
                'l10n_be_capped_amount': capped_amount or False,
            })
        else:
            base_version[wage_field] = new_wage
            base_version.l10n_be_capped_amount = capped_amount

    def _index_future_versions(self, future_versions):
        self.ensure_one()
        if self.type == 'legal':
            return
        super()._index_future_versions(future_versions)

    def _generate_indexation_message(self, future_affected_versions):
        if self.type == 'manual':
            return super()._generate_indexation_message(future_affected_versions)

        egov3_code = self.employee_ids[:1].l10n_be_egov3_code
        rule_parameters = self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_be_legal_index',
            date=date(int(self.year), 1, 1),
            raise_if_not_found=False,
        )
        params = rule_parameters.get(egov3_code) if rule_parameters and egov3_code else None
        rate, cap = params if params else (0.0, False)
        return self.env._(
            'Wage legally indexed by %(percentage).2f%%%(capped)s starting from %(increase_date)s on %(date)s.',
            percentage=rate * 100,
            capped=self.env._(' (capped at %(cap)s)', cap=self.currency_id.format(cap)) if cap else '',
            increase_date=format_date(self.env, fields.Date.to_date(f"{self.year}-01-01")),
            date=format_date(self.env, fields.Date.today()),
        )

    def _compute_increase_amount(self, current_wage, cap, rate):
        self.ensure_one()
        if cap and current_wage > cap and rate > 0.02:
            return (cap * 0.02) + (current_wage * (rate - 0.02))
        return current_wage * rate
