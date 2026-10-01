# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re
from datetime import UTC

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


class HrVersion(models.Model):
    _inherit = "hr.version"

    l10n_hk_internet = fields.Monetary(
        string="Internet Allowance",
        tracking=1,
        groups="hr_payroll.group_hr_payroll_user",
        help="A fully taxable cash allowance added to every payslip for the employee's internet subscription.",
    )
    l10n_hk_rental_id = fields.Many2one(
        comodel_name='l10n_hk.rental',
        string='Current Rental',
        compute='_compute_current_rental',
        groups="hr_payroll.group_hr_payroll_user",
        tracking=1,
    )
    l10n_hk_rental_valid_up_to_date = fields.Date(
        string='Proof Expiry Date',
        compute='_compute_current_rental',
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_hk_mpf_exempt = fields.Boolean(
        string="Exempt of MPF",
        help="Enable this to disable mandatory contributions. Voluntary contributions can still be used regardless of this setting.",
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    l10n_hk_mpf_registration_status = fields.Selection(
        string="Registration Status",
        help="When set to 'Next Contribution', the employee registration will be handled automatically through the next eMPF Contributions Report.",
        selection=[
            ('next_contribution', "Register At Next Contribution"),
            ('registered', "Registered"),
            ('terminated', "Terminated"),
        ],
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    l10n_hk_mpf_contribution_start = fields.Selection(
        string="Start Contribution",
        help="Set this to 'Immediately' to start registering contributions through the eMPF Contributions Report as soon as the employee is registered for MPF. "
             "If Set to 'At Due Date', the contributions will only start after the 60 days period, and back-payments records will be added to the report if needed.",
        selection=[
            ('immediate', "Immediately Upon Registration"),
            ('at_due_date', "At Due Date"),
        ],
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    l10n_hk_mpf_scheme_id = fields.Many2one(
        comodel_name='l10n_hk.mpf.scheme',
        string="MPF Scheme",
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('employer_account_number', '!=', False)]",
        tracking=True,
    )
    l10n_hk_payroll_group_id = fields.Many2one(
        comodel_name='l10n_hk.payroll.group',
        string="Payroll Group",
        help="Precising the group is optional, but becomes mandatory if the company uses more than one group for the employee scheme.",
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('company_id', '=', company_id), ('scheme_id', '=', l10n_hk_mpf_scheme_id)]",
        compute='_compute_l10n_hk_payroll_group',
        store=True,
        tracking=True,
        readonly=False,
    )
    l10n_hk_member_class_id = fields.Many2one(
        comodel_name='l10n_hk.member.class',
        string="Member Class",
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('company_id', '=', company_id), ('scheme_id', '=', l10n_hk_mpf_scheme_id)]",
        compute='_compute_l10n_hk_member_class',
        store=True,
        tracking=True,
        readonly=False,
    )
    l10n_hk_mpf_account_number = fields.Char(
        string="Member Account No.",
        help="Precising the account is optional, but becomes mandatory if the employee uses more than one active member account under the same employer and payroll group.",
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    l10n_hk_mpf_scheme_join_date = fields.Date(
        string="Date of Joining the Scheme",
        help="Leave empty to set the date automatically upon registering through the eMPF Contributions Report.",
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    # This is optional, but we may as well support it.
    l10n_hk_staff_number = fields.Char(
        string="Staff No.",
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )
    l10n_hk_has_postal_address = fields.Boolean(
        string="Postal Address",
        help="Enable to input a different postal address to use when reporting to the IRD.",
        groups="hr.group_hr_user",
        tracking=True,
    )
    l10n_hk_postal_street = fields.Char(
        string="Postal Street",
        groups="hr.group_hr_user",
        tracking=True,
    )
    l10n_hk_postal_street2 = fields.Char(
        string="Postal Street2",
        groups="hr.group_hr_user",
        tracking=True,
    )
    l10n_hk_postal_city = fields.Char(
        string="Postal City",
        groups="hr.group_hr_user",
        tracking=True,
    )
    l10n_hk_postal_zip = fields.Char(
        string="Postal ZIP",
        groups="hr.group_hr_user",
        tracking=True,
    )
    l10n_hk_postal_state_id = fields.Many2one(
        "res.country.state",
        string="Postal State",
        groups="hr.group_hr_user",
        tracking=True,
        domain="[('country_id', '=?', l10n_hk_postal_country_id)]",
    )
    l10n_hk_postal_country_id = fields.Many2one(
        "res.country",
        string="Postal Country",
        groups="hr.group_hr_user",
        tracking=True,
    )
    # Technical fields
    l10n_hk_scheme_group_count = fields.Integer(
        compute="_compute_l10n_hk_scheme_group_count",
        groups='hr_payroll.group_hr_payroll_user',
        export_string_translation=False,
    )
    l10n_hk_member_class_ct_eevc_id = fields.Many2one(
        comodel_name='l10n_hk.member.class.contribution.type',
        groups='hr_payroll.group_hr_payroll_user',
        compute='_compute_employee_member_class_contribution_types',
        export_string_translation=False,
    )
    l10n_hk_member_class_ct_ervc_id = fields.Many2one(
        comodel_name='l10n_hk.member.class.contribution.type',
        groups='hr_payroll.group_hr_payroll_user',
        compute='_compute_employee_member_class_contribution_types',
        export_string_translation=False,
    )
    l10n_hk_member_class_ct_ervc2_id = fields.Many2one(
        comodel_name='l10n_hk.member.class.contribution.type',
        groups='hr_payroll.group_hr_payroll_user',
        compute='_compute_employee_member_class_contribution_types',
        export_string_translation=False,
    )

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('l10n_hk_mpf_scheme_id')
    def _compute_l10n_hk_payroll_group(self):
        """
        Set the default group on an employee when a scheme is selected.
        We do not overwrite the group if it is set to another one from the same scheme.
        If the scheme is changed to another one with no defaults, we empty the group.
        """
        default_groups = self.env['l10n_hk.payroll.group']._read_group(
            domain=[('is_default', '=', True)],
            groupby=['company_id', 'scheme_id'],
            # Schemes are shared between companies, but the groups are specific to a company.
            aggregates=['id:recordset'],
        )
        default_groups_dict = {(company, scheme): default_group for company, scheme, default_group in default_groups}
        for employee in self:
            default_group = default_groups_dict.get((employee.company_id, employee.l10n_hk_mpf_scheme_id))
            group_is_of_employee_scheme = employee.l10n_hk_payroll_group_id.scheme_id == employee.l10n_hk_mpf_scheme_id
            if default_group and not group_is_of_employee_scheme:
                employee.l10n_hk_payroll_group_id = default_group
            elif employee.l10n_hk_payroll_group_id and not group_is_of_employee_scheme:
                employee.l10n_hk_payroll_group_id = False

    @api.depends('l10n_hk_mpf_scheme_id')
    def _compute_l10n_hk_member_class(self):
        """
        Set the default member class on an employee when a scheme is selected.
        We do not overwrite the class if it is set to another one from the same scheme.
        If the scheme is changed to another one with no defaults, we empty the class.
        """
        default_classes = self.env['l10n_hk.member.class']._read_group(
            domain=[('is_default', '=', True)],
            groupby=['company_id', 'scheme_id'],
            aggregates=['id:recordset'],
        )
        default_classes_dict = {(company, scheme): default_class for company, scheme, default_class in default_classes}
        for employee in self:
            default_class = default_classes_dict.get((employee.company_id, employee.l10n_hk_mpf_scheme_id))
            class_is_of_employee_scheme = employee.l10n_hk_member_class_id.scheme_id == employee.l10n_hk_mpf_scheme_id
            if default_class and not class_is_of_employee_scheme:
                employee.l10n_hk_member_class_id = default_class
            elif employee.l10n_hk_member_class_id and not class_is_of_employee_scheme:
                employee.l10n_hk_member_class_id = False

    @api.depends('l10n_hk_mpf_scheme_id')
    def _compute_l10n_hk_scheme_group_count(self):
        """
        The payroll group is optional information if the company only has one.
        As soon as a company has more than one group for a scheme, this information becomes required.
        """
        for employee in self:
            if not employee.l10n_hk_mpf_scheme_id:
                employee.l10n_hk_scheme_group_count = 0
            else:
                employee.l10n_hk_scheme_group_count = len(employee.l10n_hk_mpf_scheme_id.payroll_group_ids)

    def _compute_employee_member_class_contribution_types(self):
        """ These shortcuts makes it easier to set up salary rules and such without the need to parse the contribution types each time.  """
        for employee in self:
            contribution_type_ids = employee.l10n_hk_member_class_id.contribution_type_ids.grouped('contribution_type')
            employee.write({
                'l10n_hk_member_class_ct_eevc_id': contribution_type_ids.get('employee', False),
                'l10n_hk_member_class_ct_ervc_id': contribution_type_ids.get('employer', False),
                'l10n_hk_member_class_ct_ervc2_id': contribution_type_ids.get('employer_2', False),
            })

    def _compute_current_rental(self):
        """
        Compute the most recent confirmed rental at the time of the version, as well as its proof expiry date.
        Rentals are not tightly linked to a version and only to an employee; so these fields serve as a shortcut to the
        most relevant rental for a given version (the most recent running one at the time).
        """
        employees_rentals = self.env["l10n_hk.rental"]._read_group(
            domain=[("employee_id", "in", self.employee_id.ids), ('state', '=', 'confirmed')],
            groupby=["employee_id"],
            aggregates=['id:recordset'],
        )
        employees_rentals = dict(employees_rentals or {})
        for version in self:
            employee_rentals = employees_rentals.get(version.employee_id)
            if not employee_rentals:
                valid_rentals = None
            elif not version.date_end:  # Most recent one that is still running
                valid_rentals = employee_rentals.filtered(
                    lambda r: not r.date_end or r.date_end >= fields.Date.context_today(version)
                )
            else:  # Most recent one from before the end date.
                valid_rentals = employee_rentals.filtered(
                    lambda r: r.date_start < version.date_end and (not r.date_end or r.date_end >= version.date_end)
                )
            current_rental = valid_rentals[0] if valid_rentals else self.env['l10n_hk.rental']
            version.l10n_hk_rental_id = current_rental
            version.l10n_hk_rental_valid_up_to_date = current_rental.valid_up_to_date

    # ----------------------------
    # Onchange, Constraint methods
    # ----------------------------

    @api.constrains('l10n_hk_staff_number')
    def _contraints_staff_number(self):
        """ Enforce the format required by the eMPF system. """
        for version in self:
            if version.l10n_hk_staff_number and not re.match(r'^[a-zA-Z0-9]{,20}$', version.l10n_hk_staff_number):
                raise ValidationError(
                    self.env._(
                        "The Staff Number must be a maximum of 20 characters and can only contain letters (a-Z) and numbers (0-9). "
                        "Please do not use spaces or symbols.")
                )

    # ----------------
    # Business methods
    # ----------------

    def _get_commencement_date_for_vesting(self):
        """ Returns the commencement date based on the option set on the member class of the employee. """
        self.ensure_one()
        if not self.l10n_hk_member_class_id:
            return None

        date_field_name = start_date = None
        match self.l10n_hk_member_class_id.definition_of_service:
            case 'date_of_employment':
                start_date = self.employee_id._get_first_version_date()
            case 'date_of_joining_scheme':
                start_date = self.l10n_hk_mpf_scheme_join_date
            case 'previous_date_of_employment':
                start_date = self.l10n_hk_previous_employment_date

        # Fallback to the _get_first_version_date if the definition_of_service doesn't match the expected values; but it shouldn't happen.
        start_date = start_date or self.employee_id._get_first_version_date()
        if not start_date:
            start_date_string = self._fields[date_field_name].get_description(self.env)["string"]
            raise UserError(
                self.env._(
                    "You must set the %(start_date_string)s for employee %(employee_name)s in order to properly calculate the vested percentage.",
                    start_date_string=start_date_string,
                    employee_name=self.name,
                )
            )
        return start_date
    l10n_hk_leaving_hk = fields.Boolean(related='departure_id.l10n_hk_leaving_hk', readonly=False, groups="hr.group_hr_user")

    def _get_bypassing_work_entry_type_codes(self):
        return super()._get_bypassing_work_entry_type_codes() + [
            'HKLEAVE210',  # Maternity Leave
            'HKLEAVE211',  # Maternity Leave 80%
            'HKLEAVE220',  # Paternity Leave
            'HKLEAVE112',  # Work Injury Sick Leave 80%
        ]

    def _get_interval_leave_work_entry_type(self, interval, leaves, bypassing_codes):
        self.ensure_one()
        if not self._is_struct_from_country('HK'):
            return super()._get_interval_leave_work_entry_type(interval, leaves, bypassing_codes)

        interval_start = interval[0].astimezone(UTC).replace(tzinfo=None)
        interval_stop = interval[1].astimezone(UTC).replace(tzinfo=None)

        including_rcleaves = [leave[2] for leave in leaves if leave[2] and interval_start >= leave[2].date_from and interval_stop <= leave[2].date_to]
        including_global_rcleaves = [leave for leave in including_rcleaves if not leave.holiday_id]
        including_holiday_rcleaves = [leave for leave in including_rcleaves if leave.holiday_id]
        statutory_holiday_rcleaves = [leave for leave in including_global_rcleaves if leave.work_entry_type_id.code == 'HKLEAVE500']

        bypassing_rc_leave = False
        if bypassing_codes:
            bypassing_rc_leave = [leave for leave in including_holiday_rcleaves if leave.holiday_id.work_entry_type_id.code in bypassing_codes]
        bypassing_weekend_codes = ['158.00']
        bypassing_weekend_rc_leave = [leave for leave in including_holiday_rcleaves if leave.holiday_id.work_entry_type_id.code in bypassing_weekend_codes]

        # Maternity Leave, Paternity Leave > Statutory Holiday > Unpaid Leave, Sick Leave > Public Holiday
        rc_leave = False
        if bypassing_rc_leave:
            rc_leave = bypassing_rc_leave[0]
        elif statutory_holiday_rcleaves:
            rc_leave = statutory_holiday_rcleaves[0]
        elif bypassing_weekend_rc_leave:
            rc_leave = bypassing_weekend_rc_leave[0]
        elif including_global_rcleaves:
            rc_leave = including_global_rcleaves[0]
        if rc_leave:
            return self._get_leave_work_entry_type_dates(rc_leave, interval_start, interval_stop, self.employee_id)

        # Weekend > Other Leave > AL
        if 'work_entry_type_id' in interval[2] and interval[2].work_entry_type_id.code == 'HKLEAVE600':
            return interval[2].work_entry_type_id
        if including_holiday_rcleaves:
            return self._get_leave_work_entry_type_dates(including_holiday_rcleaves[0], interval_start, interval_stop, self.employee_id)
        return self.env.ref('hr_work_entry.hk_work_entry_type_leave')

    def _get_fields_that_recompute_payslip(self):
        return super()._get_fields_that_recompute_payslip() + ['l10n_hk_internet']

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "HK":
            whitelisted_fields += [
                'l10n_hk_internet',
            ]
        return whitelisted_fields
