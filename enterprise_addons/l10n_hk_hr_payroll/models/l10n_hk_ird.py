# Part of Odoo. See LICENSE file for full copyright and licensing details.

from codecs import BOM_UTF8
from collections import defaultdict
from datetime import date
from re import sub

from dateutil.relativedelta import relativedelta
from lxml.html import etree
from markupsafe import Markup

from odoo import api, fields, models
from odoo.addons.phone_validation.tools import phone_validation
from odoo.exceptions import UserError
from odoo.fields import Command, Domain
from odoo.tools import format_date, split_every, float_round
from odoo.tools.misc import file_path, default_parser

MONTH_SELECTION = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
    ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
    ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December'),
]
AREA_CODE_MAP = {
    'HK': 'H',      # Hong Kong Island
    'KLN': 'K',     # Kowloon
    'NT': 'N',      # New Territories
    # 'F' is used as a default for foreign or unspecified areas later in the code.
}


class L10n_HkIrd(models.AbstractModel):
    _name = 'l10n_hk.ird'
    _inherit = ['hr.payroll.declaration.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'IRD Sheet'
    _order = 'start_period'

    # ---------------
    # Default methods
    # ---------------

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != 'HK':
            raise UserError(self.env._('You must be logged in a Hong Kong company to use this feature.'))
        if not self.env.company.l10n_hk_employer_name or not self.env.company.l10n_hk_employer_file_number:
            raise UserError(self.env._("Please configure the Employer's Name and the Employer's File Number in the company settings."))
        return super().default_get(fields)

    # ------------------
    # Fields declaration
    # ------------------

    display_name = fields.Char()
    state = fields.Selection([('draft', 'Draft'), ('waiting', 'Waiting'), ('done', 'Done')], default='draft')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    start_year = fields.Integer(required=True, default=lambda self: fields.Date.context_today(self).year - 1)
    start_month = fields.Selection(MONTH_SELECTION, required=True, default='4')
    start_period = fields.Date('Start Period', compute='_compute_period', store=True)
    end_year = fields.Integer(required=True, default=lambda self: fields.Date.context_today(self).year)
    end_month = fields.Selection(MONTH_SELECTION, required=True, default='3')
    end_period = fields.Date('End Period', compute='_compute_period', store=True)
    submission_date = fields.Date('Submission Date', default=fields.Date.context_today, required=True, tracking=True)
    year_of_employer_return = fields.Char("Year of Employer's Return", tracking=True)
    name_of_signer = fields.Char("Name of Signer", required=True, tracking=True)
    designation_of_signer = fields.Char("Designation of Signer", required=True, tracking=True)
    type_of_form = fields.Selection(
        selection=[('O', "Original"), ('ARS', "Additional/Replacement/Supplementary")],
        string="Type Of Form",
        tracking=True,
        compute='_compute_type_of_form',
        store=True,
        readonly=False,
    )
    separate_original_from_adjustments = fields.Boolean(compute='_compute_separate_original_from_adjustments')

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('start_year', 'start_month', 'end_year', 'end_month')
    def _compute_period(self):
        for record in self:
            record.start_period = date(record.start_year, int(record.start_month), 1)
            record.end_period = date(record.end_year, int(record.end_month), 1) + relativedelta(day=31)

    @api.depends('start_period')
    def _compute_display_name(self):
        for sheet in self:
            if sheet.start_period:
                sheet.display_name = format_date(self.env, sheet.start_period, date_format="MMMM y", lang_code=self.env.user.lang or 'en_US')
            else:
                sheet.display_name = self.env._("IRD Sheet")

    @api.depends('separate_original_from_adjustments')
    def _compute_type_of_form(self):
        for sheet in self:
            if sheet.separate_original_from_adjustments:
                sheet.type_of_form = 'O'
            else:
                sheet.type_of_form = False

    def _compute_separate_original_from_adjustments(self):
        """
        Set to True if this declaration is separating the original records from the adjustments.
        This is done, for now, by the IR56B and M.
        """
        self.separate_original_from_adjustments = False

    # ----------------------------
    # Onchange, Constraint methods
    # ----------------------------

    @api.constrains('year_of_employer_return')
    def _check_year_of_employer_return(self):
        for report in self.filtered(lambda c: c.year_of_employer_return):
            if year := report.year_of_employer_return:
                if not year.isdecimal() or len(year) != 4:
                    raise UserError(self.env._("The year of employer's return must be a 4 digits number."))
                if int(year) > fields.Date.today().year:
                    raise UserError(self.env._("The year of employer's return must be in the past."))

    # --------------
    # Action methods
    # --------------

    def action_generate_declarations(self):
        """
        This action will load the list of eligible employees for the report.
        It will pick all eligible payslips for the period, and apply the domain returned from _get_report_version_domain
        to the search so that the employees to pick can be chosen specifically to each child reports.
        """
        for sheet in self:
            all_versions = self.env['hr.version'].with_context(active_test=False).search(
                sheet._get_report_version_domain(),
            )

            # Find declarations for a same report that overlap with this one, to avoid reporting the same employee twice.
            sheet_domain = sheet._get_report_sheet_domain()
            reported_versions = self.env[sheet._name].search(sheet_domain).line_ids.version_id
            versions_to_report = all_versions - reported_versions

            # Last check is to see if the employees `_get_first_version_date` fall in the reported period too.
            # If not, it is a continuous employment and the employee should be exempted
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

    def action_generate_xml(self):
        """
        Generates the XML file(s) that can be reported to the government.
        It will create one file per batch of 5000 employees, as required by the standard.

        Note that this will fail if the specific IR report doesn't define the report filename and template.
        """
        self.ensure_one()
        multiple_files = len(self.line_ids.employee_id) > 5000

        attachments_data = []
        data = self._get_rendering_data(self.line_ids.employee_id)
        if 'error' in data:
            raise UserError(data['error'])

        base_data = data.copy()
        # We do the split after rendering the data, as we want the sequence in the employees_data to be continuous even
        # if we use multiple files.
        for i, employees_data in enumerate(split_every(5000, data['employees_data'])):
            xml_str = self.env['ir.qweb']._render(self._get_xml_report_template(), {
                **base_data,
                'employees_data': employees_data,
            })

            # Prettify xml string
            root = etree.fromstring(xml_str, parser=default_parser)
            # We directly validate the xml file, in case of error in any of the file we provide the error and stop the process immediately.
            if errors := self._validate_xml_report_file(root):
                self.message_post(
                    body=self.env._(
                        "The generated XML file failed to pass the validation."
                        "%(br)s%(errors)s",
                        br=Markup("<br/>"),
                        errors=errors,
                    ),
                    attachments=[(
                        self._get_xml_report_filename(file_number='error'),
                        BOM_UTF8 + etree.tostring(root, pretty_print=True, encoding='UTF-8', xml_declaration=True, standalone=True),
                    )],
                )
                return

            attachments_data.append({
                'name': self._get_xml_report_filename(file_number=i if multiple_files else False),
                'raw': BOM_UTF8 + etree.tostring(root, pretty_print=True, encoding='UTF-8', xml_declaration=True, standalone=True),
                'mimetype': 'application/xml',
                'res_model': self._name,
                'res_id': self.id,
            })

        new_files = self.env['ir.attachment'].create(attachments_data)
        self.message_post(
            body=self.env._("The IRD reports were successfully generated."),
            attachment_ids=new_files.ids,
        )
        self.state = 'waiting'

    def action_open_declarations(self):
        action = super().action_open_declarations()
        action['context']['show_type_of_form'] = not self.separate_original_from_adjustments or self.type_of_form == 'ARS'
        return action

    # ----------------
    # Business methods
    # ----------------

    def _country_restriction(self):
        return 'HK'

    @api.model
    def _get_xml_resource(self, file_name):
        return file_path(f'l10n_hk_hr_payroll/data/xml_schema/{file_name}')

    def _validate_employee_addresses(self, employees):
        invalid_employees = employees.filtered(lambda e: not e.private_street or not e.private_state_id)
        if invalid_employees:
            return self.env._("The following employees don't have a valid private address (with a street and an area code): %s", ', '.join(invalid_employees.mapped('name')))
        invalid_postal_employees = employees.filtered(lambda e: e.l10n_hk_has_postal_address and (not e.l10n_hk_postal_street or not e.l10n_hk_postal_state_id))
        if invalid_postal_employees:
            return self.env._("The following employees don't have a valid postal address (with a street and an area code): %s", ', '.join(invalid_postal_employees.mapped('name')))
        return None

    def _validate_employee_personal_info(self, employees):
        invalid_employees = employees.filtered(lambda e: not e.l10n_hk_surname or not e.l10n_hk_given_name or not e.sex)
        if invalid_employees:
            return self.env._("Please configure a surname, a given name and a sex for the following employees: %s", ', '.join(invalid_employees.mapped('name')))
        return None

    def _validate_employee_identification(self, employees):
        invalid_employees = employees.filtered(lambda e: not e.identification_id and not e.passport_id)
        if invalid_employees:
            return self.env._("Please configure a HKID or a passport number for the following employees: %s", ', '.join(invalid_employees.mapped('name')))
        missing_passport_country_employees = employees.filtered(lambda e: not e.identification_id and e.passport_id and not e.l10n_hk_passport_place_of_issue)
        if missing_passport_country_employees:
            return self.env._("Please configure the passport's Place of Issue for the following employees: %s", ', '.join(missing_passport_country_employees.mapped('name')))
        return None

    def _validate_employee_rental_records_count(self, employees):
        """ Note, this is a warning more than something we want to be blocking; so we log the warning in the chatter. """
        employees_rentals = self.env["l10n_hk.rental"]._read_group(
            domain=[
                ("employee_id", "in", employees.ids),
                ('state', '=', 'confirmed'),
                ('date_start', '<=', self.end_period),
                '|',
                ('date_end', '>', self.start_period),
                ('date_end', '=', False),
            ],
            groupby=["employee_id"],
            having=[('__count', '>', 2)],
        )
        if invalid_employees := self.env['hr.employee'].browse([employee[0].id for employee in employees_rentals]):
            warning = self.env._("Some employee have more than 2 rental records within the period:\n%s", '\n'.join(invalid_employees.mapped('name')))
            self._message_log(body=warning)

    def _validate_employee_rental_records(self, employees):
        """
        We want to raise an error in case of inconsistent data
        (posted payslip linked to now draft or archived rentals, which would affect the report)
        """
        all_payslips = self.env['hr.payslip'].search(
            domain=[
                ("employee_id", "in", employees.ids),
                ('state', 'in', ['validated', 'paid']),
                ('date_from', '>=', self.start_period),
                ('date_to', '<=', self.end_period),
            ],
        )
        invalid_payslips = all_payslips.filtered(
            lambda s: s.l10n_hk_rental_id and (s.l10n_hk_rental_id.state != 'confirmed' or not s.l10n_hk_rental_id.active)
        )
        if invalid_employees := invalid_payslips.employee_id:
            return self.env._("The following employees have posted payslips linked to a 'Draft' or 'Archived' rental record."
                              "Please validate their rental records before generating the IRD report:\n%s", '\n'.join(invalid_employees.mapped('name')))
        return None

    def _check_employees(self, employees):
        self.ensure_one()
        if not employees:
            return self.env._("You must select at least one employee.")

        error_messages = []
        error_messages.append(self._validate_employee_addresses(employees))
        error_messages.append(self._validate_employee_personal_info(employees))
        error_messages.append(self._validate_employee_identification(employees))
        error_messages.append(self._validate_employee_rental_records_count(employees))
        error_messages.append(self._validate_employee_rental_records(employees))

        invalid_employees = self.line_ids.filtered(lambda e: not e.l10n_hk_hr_payroll_type_of_form).employee_id
        if invalid_employees:
            return self.env._("The following employees don't have a Type Of Form set: %s", ', '.join(invalid_employees.mapped('name')))

        return '\n'.join(filter(None, error_messages))

    def _get_employees_payslip_data(self, employees):
        self.ensure_one()
        all_payslips = self.env['hr.payslip'].search([
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', self.start_period),
            ('date_to', '<=', self.end_period),
            ('employee_id', 'in', employees.ids),
            ('struct_id.country_id', '=', self.env.ref('base.hk').id),
        ])

        if not all_payslips:
            raise UserError(self.env._('There are no confirmed payslips using the CAP57 structure for the selected employees in this period.'))

        employee_payslips_map = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in all_payslips:
            employee_payslips_map[payslip.employee_id] |= payslip

        return {'all_payslips': all_payslips, 'employee_payslips_map': employee_payslips_map}

    def _get_report_info_data(self):
        self.ensure_one()
        file_number = ''
        company = self.company_id
        if company.l10n_hk_employer_file_number:
            file_number = company.l10n_hk_employer_file_number.strip()
        section, ern = file_number.split('-')

        company_address_parts = [
            company.street, company.street2, company.city,
            company.state_id.name if company.state_id else None,
            company.country_id.name if company.country_id else None
        ]
        company_address = ', '.join(filter(None, company_address_parts))

        return {
            'FileNo': file_number,
            'Section': section,
            'ERN': ern.upper(),
            'YrErReturn': self.year_of_employer_return if self.type_of_form == 'O' else '',
            'SubDate': self.submission_date,
            'ErName': company.l10n_hk_employer_name,
            'company_address': company_address,
            'NAME_OF_SIGNER': self.name_of_signer,
            'Designation': self.designation_of_signer,
        }

    def _get_employee_data(self, employee):
        hkid = employee.identification_id.strip().upper() if employee.identification_id else ''
        raw_phone = employee.private_phone or employee.work_phone or employee.mobile_phone or ''
        phone_nbr = ''
        if raw_phone:
            region_data = phone_validation.phone_get_region_data_for_number(raw_phone)
            phone_nbr = region_data.get('national_number')
            if not phone_nbr:
                phone_nbr = sub(r'\D', '', raw_phone)
                if phone_nbr.startswith('852') and len(phone_nbr) > 8:
                    phone_nbr = phone_nbr[3:]

        employee_data = {
            'employee': employee,
            'employee_id': employee.id,
            'HKID': hkid,
            'Surname': employee.l10n_hk_surname or '',
            'GivenName': employee.l10n_hk_given_name or '',
            'NameInChinese': employee.l10n_hk_name_in_chinese or '',
            'Sex': 'M' if employee.sex == 'male' else 'F',
            'PpNum': f'{employee.passport_id}, {employee.l10n_hk_passport_place_of_issue}' if not hkid else '',
            'RES_ADDR_LINE1': employee.private_street or '',
            'RES_ADDR_LINE2': employee.private_street2 or '',
            'RES_ADDR_LINE3': ', '.join(filter(None, [employee.private_city, employee.private_zip])),
            'employee_address': ', '.join(filter(None, [
                employee.private_street, employee.private_street2, employee.private_city, employee.private_zip,
                employee.private_state_id.name, employee.private_country_id.name
            ])),
            'AreaCodeResAddr': AREA_CODE_MAP.get(employee.private_state_id.code, 'F'),
            'POS_ADDR_LINE1': '',
            'POS_ADDR_LINE2': '',
            'POS_ADDR_LINE3': '',
            'POS_ADDR_AREA': '',
            'postal_address': '',
            'Capacity': employee.job_title or '',
            'date_of_commencement': employee._get_first_version_date(),
            'PhoneNum': phone_nbr,
        }

        if employee.l10n_hk_has_postal_address:
            employee_data.update({
                'POS_ADDR_LINE1': employee.l10n_hk_postal_street or '',
                'POS_ADDR_LINE2': employee.l10n_hk_postal_street2 or '',
                'POS_ADDR_LINE3': ', '.join(filter(None, [
                    employee.l10n_hk_postal_city, employee.l10n_hk_postal_zip,
                ])),
                'POS_ADDR_AREA': AREA_CODE_MAP.get(employee.l10n_hk_postal_state_id.code, 'F'),
                'postal_address': ', '.join(filter(None, [
                    employee.l10n_hk_postal_street, employee.l10n_hk_postal_street2, employee.l10n_hk_postal_city, employee.l10n_hk_postal_zip,
                    employee.l10n_hk_postal_state_id.name, employee.l10n_hk_postal_country_id.name,
                ])),
            })

        return employee_data

    def _get_employee_spouse_data(self, employee):
        data = {
            'SpouseName': '',
            'SpouseHKID': '',
            'SpousePpNum': '',
            'MaritalStatus': 2 if employee.marital == 'married' else 1,
        }

        if employee.marital == 'married':
            data['SpouseName'] = employee.spouse_complete_name.upper() if employee.spouse_complete_name else ''
            data['SpouseHKID'] = employee.l10n_hk_spouse_identification_id.strip().upper() if employee.l10n_hk_spouse_identification_id else ''
            data['SpousePpNum'] = ', '.join(filter(None, [employee.l10n_hk_spouse_passport_id, employee.l10n_hk_spouse_passport_place_of_issue]))

        return data

    def _get_employee_rental_data(self, employee, payslips, all_line_values):
        """
        Calculate the rental data for the provided employee and payslips.
        The logic is a bit complex, mostly due to the need to report the accurate totally paid amount by the employee.
        This isn't something we have ready anywhere; we need to calculate it by taking into account possible changes in rent
        amount and such.
        """
        self.ensure_one()

        def get_total(code, lines_value, rental_payslips):
            total = 0.0
            rule_values = lines_value.get(code, {})
            for p in rental_payslips:
                total += rule_values.get(p.id, {}).get('total', 0)
            return self._format_ird_amount(total)

        employee_start_date = employee._get_first_version_date()
        employee_departure_date = employee.departure_date
        start_date = max(self.start_period, employee_start_date)
        rental_ids = self.env["l10n_hk.rental"].search(
            domain=[
                ("employee_id", "in", employee.ids),
                ('state', '=', 'confirmed'),
                ('date_start', '<=', self.end_period),
                '|',
                ('date_end', '>', start_date),
                ('date_end', '=', False),
            ],
        )
        grouped_rentals = rental_ids.grouped('address')  # Important! We need to report a same address only once.

        data = {
            'PlaceOfResInd': int(bool(rental_ids)),
            'AddrOfPlace1': '',
            'NatureOfPlace1': '',
            'PerOfPlace1': '',
            'RentPaidEr1': 0,
            'RentPaidEe1': 0,
            'RentRefund1': 0,
            'RentPaidErByEe1': 0,
            'AddrOfPlace2': '',
            'NatureOfPlace2': '',
            'PerOfPlace2': '',
            'RentPaidEr2': 0,
            'RentPaidEe2': 0,
            'RentRefund2': 0,
            'RentPaidErByEe2': 0,
        }

        for count, (address, rentals) in enumerate(grouped_rentals.items(), start=1):
            if count > 2:
                break
            sorted_rentals = rentals.sorted('date_start')

            effective_start = max(sorted_rentals[0].date_start, start_date, employee_start_date)
            effective_end = min(sorted_rentals[-1].date_end or self.end_period, self.end_period, employee_departure_date or self.end_period)
            data.update({
                'AddrOfPlace%s' % count: address,
                'NatureOfPlace%s' % count: sorted_rentals[-1].nature,
                'PerOfPlace%s' % count: '{} - {}'.format(
                    effective_start.strftime('%Y%m%d'),
                    effective_end.strftime('%Y%m%d')
                ),
            })
            # We report the rentals per address; so we need to sum the amounts of all rentals of a same address.
            for rental in sorted_rentals:
                date_start_rental = max(rental.date_start, start_date, employee_start_date)
                date_end_rental = min(rental.date_end or self.end_period, self.end_period, employee_departure_date or self.end_period)
                # Filter the payslips to only keep the ones that match the current rental
                payslips_rental = payslips.filtered_domain([
                    ('state', 'in', ['validated', 'paid']),
                    ('date_from', '<=', date_end_rental),
                    ('date_to', '>=', date_start_rental),
                ]).sorted('date_from')

                reimbursed_amount = get_total('HRA', all_line_values, payslips_rental)
                employer_paid_rent = get_total('HEPR', all_line_values, payslips_rental)
                employee_rent_contribution = get_total('HC', all_line_values, payslips_rental)
                employee_paid_rent = rental._get_rent_amount_in_period(date_start_rental, date_end_rental)

                match rental.lease_type:
                    case 'reimbursement':
                        data['RentPaidEe%s' % count] += abs(employee_paid_rent)
                        data['RentRefund%s' % count] += abs(reimbursed_amount)
                    case 'direct_payment':
                        data['RentPaidEr%s' % count] += abs(employer_paid_rent)
                    case 'co_payment':
                        data['RentPaidEr%s' % count] += abs(employer_paid_rent)
                        data['RentPaidErByEe%s' % count] += abs(employee_rent_contribution)
        return data

    def _get_employee_rap_data(self, payslips, all_line_values):
        """
        Calculate and return the amounts for the Rewards, Allowances, and Perquisites for the given employee.
        """
        self.ensure_one()

        rap_rules = payslips.struct_id._l10n_hk_get_rules_per_categories()['ALLOWANCE_RAP']

        total_per_code = defaultdict(float)
        for code, values in all_line_values.items():
            if code in rap_rules:
                for payslip in payslips:
                    total_per_code[code] += all_line_values[code].get(payslip.id, {})['total']

        totals = list(total_per_code.items())
        rap_amount = len(totals)

        rap_data = {
            'NatureOtherRAP1': '',
            'AmtOfOtherRAP1': 0,
            'NatureOtherRAP2': '',
            'AmtOfOtherRAP2': 0,
            'NatureOtherRAP3': '',
            'AmtOfOtherRAP3': 0,
        }
        if rap_amount >= 1:
            code, total = totals[0]
            rap_name = rap_rules[code].name
            rap_data.update({
                'NatureOtherRAP1': rap_name,
                'AmtOfOtherRAP1': self._format_ird_amount(total),
            })
        if rap_amount >= 2:
            code, total = totals[1]
            rap_name = rap_rules[code].name
            rap_data.update({
                'NatureOtherRAP2': rap_name,
                'AmtOfOtherRAP2': self._format_ird_amount(total),
            })
        if rap_amount == 3:
            code, total = totals[2]
            rap_name = rap_rules[code].name
            rap_data.update({
                'NatureOtherRAP3': rap_name,
                'AmtOfOtherRAP3': self._format_ird_amount(total),
            })
        elif rap_amount >= 4:
            rap_data.update({
                'NatureOtherRAP3': 'Others',
                'AmtOfOtherRAP3': self._format_ird_amount(sum(total[1] for total in totals[2:])),
            })

        return rap_data

    def _get_report_version_domain(self):
        """
        Domain used to filter the employees that should appear in the report.
        This should pick all employees eligible for declarations in the report; a separate check will be done to remove
        those that were already declared in the same period.
        """
        self.ensure_one()
        return Domain.TRUE

    def _get_report_sheet_domain(self):
        """
        Domain used to find reports that overlap with the one in self, whose declaration lines should
        be exclusive with self.
        The employees reported in the report found with this domain will be ignored when populating self.
        """
        self.ensure_one()
        return Domain([
            ('company_id', '=', self.company_id.id),
            ('start_period', '=', self.start_period),
            ('end_period', '=', self.end_period),
            ('type_of_form', '=', self.type_of_form),
            ('id', '!=', self.id),
        ])

    def _check_continuity(self, employees_to_report):
        return employees_to_report

    def _get_xml_report_template(self):
        """ To be defined by each specific reports as needed. """
        self.ensure_one()
        raise NotImplementedError

    def _get_xml_report_filename(self, file_number=False):
        """ To be defined by each specific reports as needed. """
        self.ensure_one()
        raise NotImplementedError

    def _get_xml_report_xsd_schemas(self, type_of_form):
        """
        To be defined by each specific reports as needed.
        Returns the file path to the XSD schema used for validating the given declaration.
        """
        self.ensure_one()
        raise NotImplementedError

    def _validate_xml_report_file(self, xml_root):
        """ Validate the provided xml root with the schema corresponding to the report in self and its type of form. """
        self.ensure_one()
        schema_file_path = self._get_xml_report_xsd_schemas(self.type_of_form)
        if not schema_file_path:
            return None

        schema_root = etree.parse(schema_file_path)
        schema = etree.XMLSchema(schema_root)
        try:
            schema.assertValid(xml_root)
            return None
        except etree.DocumentInvalid as err:
            return err

    def _format_ird_amount(self, amount):
        """
        Formats monetary amounts for IRD XML reporting.
        We want to omit cents; but casting to int directly comes with the risk of being one cent below
        due to possible float representation issue.

        Instead, we use the float_round tool (which has support to avoid such issue) first, before casting.
        """
        if not amount:
            return 0
        return abs(int(float_round(amount, precision_digits=2)))
