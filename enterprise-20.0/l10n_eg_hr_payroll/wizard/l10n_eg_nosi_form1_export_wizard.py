from odoo import models


class L10nEgNosiForm1Wizard(models.TransientModel):
    _name = 'l10n.eg.nosi.form1.wizard'
    _description = 'Egypt NOSI Form 1 Wizard'
    _inherit = 'l10n.eg.nosi.export.wizard'

    def action_generate_report(self):
        self.ensure_one()
        company_fields = {
            "name": self.env._("Company Name"),
            "l10n_eg_nosi_code": self.env._("Company NOSI Code"),
        }
        employee_fields = {
            "l10n_eg_ssn": self.env._("Social Security No"), "identification_id": self.env._("Identification Number"),
            "name": self.env._("Employee Name"), "country_id": self.env._("Nationality"),
            "job_id": self.env._("Job Position"),
            "l10n_eg_nosi_registration_start_date": self.env._("NOSI Registration Start Date"),
            "wage": self.env._("Basic Salary"),
            "l10n_eg_social_insurance_reference": self.env._("Social Insurance Reference Amount"),
            "private_phone": self.env._("Private Phone Number"), "private_email": self.env._("Private Email"),
            "address_id": self.env._("Address"),
        }
        headers = [
            "Company Name", "Company NOSI Code", "Social Security No", "Identification Number", "Name",
            "Nationality", "Job Position", "NOSI Registration Start Date", "Basic Salary",
            "Social Insurance Reference Amount", "Total Salary", "Phone Number", "Email", "Address",
        ]

        def data_mapper(employee):
            total_salary = (
                employee.wage + employee.version_id.l10n_eg_housing_allowance +
                employee.version_id.l10n_eg_transportation_allowance + employee.version_id.l10n_eg_other_allowances
            )
            addr = employee.address_id
            address_parts = [addr.street, addr.street2, addr.city, addr.state_id.name, addr.zip, addr.country_id.name]
            address = ", ".join(part for part in address_parts if part)
            return [
                employee.company_id.name or "", employee.company_id.l10n_eg_nosi_code or "",
                employee.l10n_eg_ssn or "", employee.identification_id or "", employee.name or "",
                employee.country_id.name or "", employee.sudo().job_id.name or "",
                employee.l10n_eg_nosi_registration_start_date, employee.wage,
                employee.l10n_eg_social_insurance_reference, total_salary,
                employee.private_phone or "", employee.private_email or "", address,
            ]

        money_spec = {"num_format": "#,##0.00", "border": 1}
        date_spec = {"num_format": "yyyy-mm-dd", "border": 1}
        column_formats = [
            None, None, None, None, None, None, None, date_spec, money_spec, money_spec,
            money_spec, None, None, None,
        ]

        return self._export_nosi_form_generic(
            form_name="NOSI Form 1", file_name="NOSI_Form_1_Export.xlsx",
            company_mandatory_fields=company_fields, employee_mandatory_fields=employee_fields,
            headers=headers, data_mapper_func=data_mapper, column_formats=column_formats
        )
