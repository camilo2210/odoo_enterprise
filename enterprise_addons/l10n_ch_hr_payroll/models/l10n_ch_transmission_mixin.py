# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import re
import time
from datetime import UTC

from odoo.exceptions import ValidationError
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes


class L10nCHSwissdecTransmitter(models.AbstractModel):
    _name = 'l10n.ch.swissdec.transmitter'
    _inherit = 'mail.thread'
    _description = 'Abstract Swissdec Transmitter'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "CH":
            raise UserError(_('You must be logged in a Swiss company to use this feature'))
        return super().default_get(fields)

    def _get_default_name(self):
        now = fields.Datetime.now()
        month = now.month
        year = now.year
        return _("Declaration %(month)s/%(year)s", month=month, year=year)

    active = fields.Boolean(default=True)
    name = fields.Char(required=True, default=_get_default_name)
    year = fields.Integer(string="Year", required=True, default=lambda self: fields.Date.context_today(self).year)
    month = fields.Selection(string="Month", selection=[
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], required=True, default=lambda self: str((fields.Date.context_today(self)).month))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, domain="[('partner_id.country_id.code', '=', 'CH')]")

    l10n_ch_declare_salary_data = fields.Json()
    actionable_warnings = fields.Json(compute="_compute_actionable_warnings", store=True)

    l10n_ch_swissdec_declaration_ids = fields.One2many("l10n.ch.swissdec.declaration", "res_id")
    l10n_ch_swissdec_declaration_ids_size = fields.Integer(compute="_compute_l10n_ch_swissdec_declaration_ids_size")

    replacement_declaration = fields.Boolean()
    substituted_declaration_id = fields.Many2one("l10n.ch.swissdec.declaration", domain=lambda self: [('res_model', '=', self._name)], string="Declaration To Substitute")

    test_transmission = fields.Boolean(string="Test Transmission")
    attachment_ids = fields.One2many('ir.attachment', 'res_id', string='Attachments')

    @api.depends('l10n_ch_declare_salary_data')
    def _compute_actionable_warnings(self):
        for declaration in self:
            missing_entries = self.env['l10n.ch.employee.monthly.values']._find_structured_missing(declaration.l10n_ch_declare_salary_data or {})

            snapshot_warnings = {}
            if missing_entries:
                snapshot_warnings[0] = {
                    "message": _("Payslips for this month were validated without completing all the necessary information, leading to possible wrong calculations. Please recompute the Payslips of the declaration period without any missing data on your Employees."),
                    "level": "warning",
                    # listed per employee by the salary data widget
                    "missing_values": declaration._get_missing_values(missing_entries),
                }

            declaration.actionable_warnings = snapshot_warnings

    def _get_missing_values(self, missing_entries):
        """ Describe the values missing from the declaration data, with the action opening the
        record to complete each of them.

        :param list missing_entries: the missing values found in the declaration data
        :return: one dict per record field, in the order of the declaration
        """
        missing_values = {}
        for missing_dict in missing_entries:
            res_model = missing_dict.get("res_model")
            res_id = missing_dict.get("res_id")
            res_field = missing_dict.get("res_field")
            key = f"{res_model},{res_id},{res_field}"
            if not (res_model and res_id and res_field) or key in missing_values:
                continue
            record = self.env[res_model].browse(res_id).exists()
            if not record:
                continue

            employee_id = missing_dict.get("employee_id")
            if res_model == 'hr.version' and employee_id:
                employee = self.env['hr.employee'].browse(employee_id)
                action = employee._get_records_action()
                action['context'].update({
                    'version_id': res_id
                })
            else:
                if res_model == 'hr.employee':
                    employee = record
                else:
                    employee = record.employee_id if 'employee_id' in record else self.env['hr.employee']
                action = record._get_records_action()

            missing_values[key] = {
                "key": key,
                "label": record._fields[res_field].get_description(self.env, ["string"])["string"],
                "employee_id": employee.id,
                "employee_name": employee.name,
                "action": action,
            }
        return list(missing_values.values())

    def _get_employee_snapshots(self):
        """ The monthly snapshots of the employees the declaration data is prepared from. """
        self.ensure_one()
        return self.env['l10n.ch.employee.yearly.values'].search([
            ('year', '=', self.year),
            ('employee_id.company_id', '=', self.company_id.id),
        ]).monthly_value_ids

    def action_refresh_missing_data(self):
        """ Complete the values missing from the snapshots with the current employee data and prepare the
        declaration data again, without reopening the payslips of the closed pay periods. """
        self.ensure_one()
        self._get_employee_snapshots()._complete_missing_values()
        return self.action_prepare_data()

    def _validate_declaration(self):
        self.ensure_one()
        if self.actionable_warnings:
            raise ValidationError(_("Declaration data is not valid, some payslips were validated with missing information, please recompute them with valid employee information"))

    def action_prepare_data(self):
        today = fields.Date.context_today(self)
        if self.year < today.year - 1 or self.year > today.year:
            raise ValidationError(_("You can only transmit data for the current or previous year."))

    @api.depends("l10n_ch_swissdec_declaration_ids")
    def _compute_l10n_ch_swissdec_declaration_ids_size(self):
        for job in self:
            job.l10n_ch_swissdec_declaration_ids_size = len(job.l10n_ch_swissdec_declaration_ids)

    def _get_institutions(self):
        return []

    def _get_declaration(self):
        return {}

    def action_declare_salary(self):
        self.ensure_one()
        self._validate_declaration()
        declare_salary = self._get_declaration()

        result = self.env.company._l10n_ch_swissdec_request('declare_salary', data=declare_salary, is_test=self.test_transmission)
        response = result['soap_response']
        message_archive = result['request_xml']
        response_archive = result['response_xml']

        if response:
            job_key = response['JobKey']
            timestamp = fields.Datetime.from_string(response['ResponseContext']['TransmissionDate']).astimezone(UTC).replace(tzinfo=None)
            declaration = self.env["l10n.ch.swissdec.declaration"].create({
                "name": f"{self.name} - {response['ResponseContext']['DeclarationID']}",
                "res_id": self.id,
                "res_model": self._name,
                "year": self.year,
                "month": self.month,
                "test_transmission": self.test_transmission,
                "job_key": job_key,
                "swissdec_declaration_id": response['ResponseContext']['DeclarationID'],
                "transmission_date": timestamp
            })
            attachment_request = self.env['ir.attachment'].create({
                'name': _("Declaration_%s_request.xml", response['ResponseContext']['DeclarationID']),
                'raw': message_archive.encode(),
                'res_id': declaration.id,
                'res_model': declaration._name,
            })

            attachment_response = self.env['ir.attachment'].create({
                'name': _("Declaration_%s_response.xml", response['ResponseContext']['DeclarationID']),
                'raw': response_archive.encode(),
                'res_id': declaration.id,
                'res_model': declaration._name,
            })
            declaration.message_post(attachment_ids=[attachment_request.id, attachment_response.id], body=_('Salary Declaration Archive'))

            return {
                'name': _('Declaration'),
                'res_model': 'l10n.ch.swissdec.declaration',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_id': declaration.id,
                'target': "current"
            }

    def action_open_swissec_declarations(self):
        self.ensure_one()
        return {
            'name': _('Declarations'),
            'res_model': 'l10n.ch.swissdec.declaration',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
        }

    def _get_wage_statement_filename(self, employee):
        return _("Wage_statement_%(year)s_%(name)s_%(timestamp)s", year=self.year, name=employee.name, timestamp=time.time_ns())

    def _save_wage_statements(self, tax_accounting_reports):
        """ Store the wage statements rendered by the Swissdec service (one PDF per person, named after
        the employee number) on the employees, replacing their previous statement for this declaration.

        :param dict tax_accounting_reports: base64 PDF by file name
        :return: the wage statements of the employees
        """
        self.ensure_one()
        pattern = re.compile(r"_pers_([A-Za-z0-9_]+)\.pdf$")
        employees_mapped_by_registration_number = dict(
            self.env['hr.employee']._read_group(
                domain=[],
                groupby=['registration_number'],
                aggregates=['id:recordset']
            )
        )
        existing_wage_statements = self.env['hr.payroll.employee.declaration'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
        ]).grouped('employee_id')

        wage_statements = self.env['hr.payroll.employee.declaration']
        wage_statement_vals = []
        for file_name, pdf_b64 in tax_accounting_reports.items():
            match = pattern.search(file_name)
            if not match:
                continue
            registration = match.group(1)
            pdf_raw = BinaryBytes(base64.b64decode(pdf_b64))

            employee = employees_mapped_by_registration_number.get(registration, self.env['hr.employee'])
            if employee:
                vals = {
                    'pdf_filename': self._get_wage_statement_filename(employee),
                    'pdf_to_generate': False,
                    'pdf_file': pdf_raw,
                }
                if employee in existing_wage_statements:
                    existing_wage_statements[employee].write(vals)
                    wage_statements |= existing_wage_statements[employee]
                else:
                    wage_statement_vals.append({
                        'employee_id': employee.id,
                        'res_model': self._name,
                        'res_id': self.id,
                        **vals,
                    })
            else:
                attachment = self.env['ir.attachment'].create({
                    'name': f"Tax_Accounting_Report_{self.year}_{registration}.pdf",
                    'raw': pdf_raw,
                    'res_id': self.id,
                    'res_model': self._name,
                })
                self.message_post(body=_("Employee with number %s was either archived or deleted. Wage statement will not be sent automatically.", registration), attachment_ids=[attachment.id])

        wage_statements |= self.env['hr.payroll.employee.declaration'].create(wage_statement_vals)
        return wage_statements

    def action_generate_wage_statement(self, employee_number):
        """ Generate the wage statement of a single person of the declaration and post it in the chatter. """
        self.ensure_one()
        declaration = self._get_declaration()
        persons = declaration.get('SalaryDeclaration', {}).get('Company', {}).get("Staff", {}).get('Person', [])
        person_number = next((
            number for number, person in enumerate(persons, start=1)
            if person.get('Particulars', {}).get('EmployeeNumber') == employee_number
        ), False)
        if not person_number:
            raise UserError(_("Employee %s is not part of this declaration.", employee_number))

        report = self.company_id._l10n_ch_swissdec_request(
            route='generate_tax_accounting_report',
            data=declaration,
            is_test=self.test_transmission,
            from_person=person_number,
            to_person=person_number + 1,
        )
        # the statement of a person without employee is posted by _save_wage_statements
        wage_statements = self._save_wage_statements((report or {}).get("tax_accounting_reports", {}))
        for wage_statement in wage_statements:
            attachment = self.env['ir.attachment'].create({
                'name': f"{wage_statement.pdf_filename}.pdf",
                'raw': wage_statement.pdf_file,
                'res_id': self.id,
                'res_model': self._name,
            })
            self.message_post(attachment_ids=[attachment.id])
