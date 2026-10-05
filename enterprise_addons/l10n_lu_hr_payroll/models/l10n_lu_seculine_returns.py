# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class L10nLuSeculineReturns(models.Model):
    _name = 'l10n.lu.seculine.returns'
    _description = 'Luxembourg: SECULine Returns'
    _order = 'year desc, month desc'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "LU":
            raise UserError(self.env._('You must be logged in a Luxembourger company to use this feature'))
        return super().default_get(fields)

    report_file = fields.Binary(string="File", required=True)
    report_type = fields.Selection([
        ('salman', 'SALMAN'),
        ('salret', 'SALRET'),
    ])
    year = fields.Char(string="Year")
    month = fields.Selection([
        ('01', 'January'), ('02', 'February'), ('03', 'March'),
        ('04', 'April'), ('05', 'May'), ('06', 'June'),
        ('07', 'July'), ('08', 'August'), ('09', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ])
    details = fields.Text(string="Details", default="Upload & analyze to see details")
    number_of_errors = fields.Integer(string="#Errors", default=0)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    def _compute_display_name(self):
        for report in self:
            report.display_name = self.env._("SECULine Return")

    def action_l10n_lu_analyze_return_file(self):
        self.ensure_one()
        if not self.report_file:
            raise ValidationError(self.env._("Please upload a file to analyze."))

        try:
            report_content = self.report_file.content.decode()
        except UnicodeDecodeError:
            raise ValidationError(self.env._("The uploaded file does not conform to SALRET or SALMAN format."))

        lines = [line.strip() for line in report_content.splitlines() if line.strip()]
        if len(lines) <= 1:  # only header line or no line
            raise ValidationError(self.env._("The uploaded file is empty."))

        report_lines = lines[1:]  # Skip header line
        self.report_type = self._check_file_and_get_report_type(report_lines)
        self.year, self.month = self._get_report_period(report_lines, self.report_type)
        self.details = self._generate_details(self.report_type, report_lines)
        self.number_of_errors = len(report_lines)

    def _generate_details(self, report_type, data_lines):
        if report_type == "salman":
            return self._generate_salman_analysis_text(data_lines)
        if report_type == "salret":
            return self._generate_salret_analysis_text(data_lines)
        return self.env._("Unknown report type.")

    def _check_file_and_get_report_type(self, report_lines):
        first_chars = {line[0] for line in report_lines}
        delimiter_counts = {line.count(';') for line in report_lines}
        if first_chars == {'9'} and delimiter_counts == {21}:
            return 'salret'
        elif first_chars == {'1'} and delimiter_counts == {6}:
            return 'salman'
        else:
            raise ValidationError(self.env._("The uploaded file does not conform to SALRET or SALMAN format."))

    def _generate_salman_analysis_text(self, report_lines):
        year, month = self.year, self.month
        formatted_period = f"{year}-{month}"

        output_lines = [
          self.env._("In the DECSAL declaration of %(period)s, the following employee records are missing:", period=formatted_period)
        ]
        output_lines.append("")  # blank line

        for line_no, line in enumerate(report_lines, start=2):  # first line is header
            if not line:
                continue
            columns = line.split(';')
            if len(columns) <= 5:
                raise ValidationError(self.env._("Invalid line %(line)s: missing employee name information", line=line_no))
            employee_name = f"{columns[4]} {columns[5]}"
            output_lines.append(f"- {employee_name}")
        return "\n".join(output_lines)

    def _generate_salret_analysis_text(self, report_lines):
        error_descriptions = {
            1: self.env._("Two records are present for the employee: "),
            2: self.env._("Employer ID Number is wrong: "),
            3: self.env._("Employee ID Number is wrong: "),
            4: self.env._("Either duration or amount is not numeric: "),
            5: self.env._("Date should be AAAAMM where year is greater than 2018 and month between 1 and 12: "),
            7: self.env._("Unemployment amount is 0 but Unemployment duration is greater than 0: "),
            8: self.env._("Extra hours amount is 0 but Extra Hours duration is greater than 0: "),
            9: self.env._("Date cannot exceed previous month: "),
            10: self.env._("Indemnity for retired, but employee is not in an official job position: "),
            11: self.env._("Total amount of hours should not exceed 372: "),
            12: self.env._("Date year should be higher than 2018: "),
            13: self.env._(" Salary is indicated as capped but exceed the 7SSM: "),
            14: self.env._("Affiliation unexisting one month after the declaration: "),
            99: self.env._("Writing error in the sequence: "),
        }
        output_lines = [self.env._("In the latest DECSAL declaration, the following issues were found:")]
        output_lines.append("")  # blank line

        for line in report_lines:
            if not line:
                continue
            columns = line.split(';', 2)
            error_code = int(columns[1])
            error_value = columns[2]
            description = error_descriptions.get(error_code, self.env._("Unknown error code %(code)s: ", code=error_code))
            output_lines.append(f"- {description}{error_value}")
        return "\n".join(output_lines)

    def _get_report_period(self, report_lines, report_type):
        period_index = 5 if report_type == "salret" else 3
        columns = report_lines[0].split(';')
        if len(columns) <= period_index:
            raise ValidationError(self.env._("The report period field is missing from the uploaded file."))
        period = columns[period_index]
        if len(period) != 6 or not period.isdigit():
            raise ValidationError(self.env._("The report period format is incorrect. Expected format is YYYYMM."))
        return period[:4], period[4:]  # YYYYMM
