# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta
from odoo.fields import Command, Domain
from odoo.tools import format_date

from odoo import api, fields, models


class L10nPhHrPayrollDeclaration(models.AbstractModel):
    _name = 'l10n_ph_hr_payroll.declaration'
    _inherit = ['hr.payroll.declaration.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Philippines Declaration'
    _order = 'period_end_date'
    _rec_name = 'name'

    name = fields.Char(
        compute='_compute_name',
        store=True,
        readonly=False,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('done', 'Done'),
        ],
        default='draft',
        readonly=True,
        tracking=True,
    )
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    period_start_date = fields.Date(
        default=lambda s: fields.Date.today() + relativedelta(day=1, months=-1),
        tracking=True,
    )
    period_end_date = fields.Date(
        default=lambda s: fields.Date.today() + relativedelta(day=31, months=-1),
        tracking=True,
    )

    @api.depends('period_end_date')
    def _compute_name(self):
        """
        Generate a human-readable display name for the declaration sheet.

        We combine the specific declaration type (like 'Form 1601-C') with the
        formatted month and year (e.g., 'Form 1601-C - December 2024') so users
        can easily identify the record in the list view.
        """
        for sheet in self:
            declaration_name = sheet._get_declaration_name()
            if sheet.period_end_date:
                end_date = format_date(self.env, sheet.period_end_date, date_format="MMMM yyyy", lang_code=self.env.user.lang or 'en_US')
                sheet.name = f"{declaration_name} - {end_date}"
            else:
                sheet.name = declaration_name

    def action_generate_declarations(self):
        """
        Populate the declaration sheet with the correct employee contract versions.

        This method acts as a smart filter for tax/statutory reporting:
        1. It fetches all eligible employee versions for the period.
        2. It subtracts any versions that have already been reported on overlapping sheets
           so we never double-report an employee.
        3. If an employee has multiple contract versions in the same period (e.g., a
           mid-month promotion), it intelligently groups them and only attaches the
           most recent version to the report line.
        """
        for sheet in self:
            all_versions = self.env['hr.version'].with_context(active_test=False).search(
                sheet._get_report_version_domain(),
            )

            # Find declarations for a same report that overlap with this one, to avoid reporting the same employee twice.
            sheet_domain = sheet._get_report_sheet_domain()
            reported_versions = self.env[sheet._name].search(sheet_domain).line_ids.version_id
            versions_to_report = all_versions - reported_versions

            # Some reports are only applicable to new employees, so we may need further filtering to exclude employees
            # that were already employed.
            versions_to_report = sheet._check_continuity(versions_to_report)

            # We can only report one version per employee; so we keep the latest one.
            # Logic that may rely on having all versions would need to re-fetch them.
            versions_to_report_grouped = versions_to_report.grouped('employee_id')

            # Due to the usage of Many2oneReference, we cannot rely on Command.Clear to unlink the values.
            sheet.line_ids.unlink()
            # We only keep one line with the latest version set on it.
            sheet.line_ids = [
                Command.create({
                    "employee_id": employee.id,
                    "version_id": versions.sorted('date_version desc')[0].id,
                    "res_model": sheet._name,
                    "res_id": sheet.id,
                }) for employee, versions in versions_to_report_grouped.items()
            ]

        return super().action_generate_declarations()

    def action_confirm_declaration(self):
        """
        Move the state of the declaration to 'done', locking in the declaration values.
        """
        self.ensure_one()
        self.state = 'done'

    def action_draft_declaration(self):
        """
        Reset a done declaration to the draft stage, allowing to re-process it.
        """
        self.ensure_one()
        self.state = 'draft'

    def _get_declaration_name(self):
        """ To overwrite in child reports to provide the declaration name. """
        self.ensure_one()
        return self.env._("Employee Declaration")

    def _country_restriction(self):
        return 'PH'

    def _get_report_version_domain(self):
        """
        Build the search domain to find employee contract versions for this report.

        This identifies all employees who had a validated/paid payslip during the
        report period, and further ensures their contract dates actively overlap
        with the period.
        """
        self.ensure_one()
        relevant_payslips = self.env['hr.payslip'].search_read(
            domain=[
                ("state", "in", ["validated", "paid"]),
                ("company_id", "=", self.company_id.id),
                ("date_to", ">=", self.period_start_date),
                ("date_to", "<=", self.period_end_date),
            ],
            fields=['version_id'],
            order='id',
            load=None,
        )
        return Domain([
            ('company_id', '=', self.company_id.id),
            ('contract_date_start', '!=', False),
            ('contract_date_start', '<=', self.period_end_date),
            '|',
            ('contract_date_end', '=', False),
            ('contract_date_end', '>', self.period_start_date),
            ('id', 'in', {payslip['version_id'] for payslip in relevant_payslips}),
        ])

    def _get_report_sheet_domain(self):
        """
        Build a search domain to find other reports covering this exact same period.

        When we generate declarations, we use this domain to find peer reports
        (e.g., another draft 1601-C for the same month and company) so we can
        exclude their employees and prevent double-reporting someone.
        """
        self.ensure_one()
        return Domain([
            ('company_id', '=', self.company_id.id),
            ('period_start_date', '=', self.period_start_date),
            ('period_end_date', '=', self.period_end_date),
            ('id', '!=', self.id),
        ])

    def _check_continuity(self, employees_to_report):
        return employees_to_report

    def _get_relevant_structures(self):
        """
        Helper returning all structures that are to be considered for the declaration.
        By default, we take all structures for the Philippines to support custom ones.
        """
        self.ensure_one()
        return self.env['hr.payroll.structure'].search([('country_id', '=', self.env.ref('base.ph').id)])

    def _format_value(self, value, preserve_sign=False, stringify=True):
        self.ensure_one()
        if value is None:
            return ""
        if isinstance(value, bool):  # Need to catch it early, as bools are instances of int and would be formatted as such.
            return str(value) if stringify else value
        if isinstance(value, (float, int)):
            if not value:
                value = 0
            if not preserve_sign:
                value = abs(value)
            rounded_value = self.currency_id.round(value)
            return f"{rounded_value:.2f}" if stringify else rounded_value
        return str(value) if stringify else value

    def _get_previous_employment(self, employee, period_end_date=None):
        """
        Small helper to return the previous employment only if it is relevant to the current period.
        Returns an empty recordset if no previous employment is available or if it isn't relevant to the current period.
        """
        return employee._l10n_ph_get_previous_employment(period_end_date or self.period_end_date)

    def _get_effective_period_start_date(self, employee):
        """ Small helper to get the effective period end date for an employee, in case they started mid-year. """
        period_to_date = self.period_start_date
        employee_start_date = employee._get_first_contract_date()
        if employee_start_date > self.period_start_date:
            period_to_date = employee_start_date
        return period_to_date

    def _get_effective_period_end_date(self, employee, period_end_date=None):
        """ Small helper to get the effective period end date for an employee, in case they left the company. """
        period_end_date = period_end_date or self.period_end_date
        employee_departure_date = employee.departure_date
        if employee_departure_date and employee_departure_date < period_end_date:
            period_end_date = employee_departure_date
        return period_end_date
