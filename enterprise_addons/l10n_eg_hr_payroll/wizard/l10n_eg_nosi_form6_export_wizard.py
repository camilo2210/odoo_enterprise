from odoo import models
from odoo.exceptions import UserError


class L10nEgNosiForm6Wizard(models.TransientModel):
    _name = 'l10n.eg.nosi.form6.wizard'
    _description = 'Egypt NOSI Form 6 Wizard'
    _inherit = 'l10n.eg.nosi.export.wizard'

    def action_generate_report(self):
        self.ensure_one()
        company_fields = {
            "name": self.env._("Company Name"),
            "l10n_eg_nosi_code": self.env._("Company NOSI Code"),
        }
        employee_fields = {
            "l10n_eg_ssn": self.env._("Social Security No"), "identification_id": self.env._("Identification Number"),
            "name": self.env._("Employee Name"), "departure_date": self.env._("Subscription End Date"),
            "departure_reason_id": self.env._("End Reason"), "private_phone": self.env._("Private Phone Number"),
            "private_email": self.env._("Private Email"), "address_id": self.env._("Address"),
        }
        headers = [
            "Company Name", "Company NOSI Code", "Social Security No", "Identification Number", "Name",
            "Subscription End Date", "End Reason", "Phone Number", "Email", "Address",
        ]

        def extra_validation(employees):
            if any(employee.active for employee in employees):
                raise UserError(self.env._("You can only export NOSI Form 6 for archived employees."))

        def data_mapper(employee):
            addr = employee.address_id
            address_parts = [addr.street, addr.street2, addr.city, addr.state_id.name, addr.zip, addr.country_id.name]
            address = ", ".join(part for part in address_parts if part)
            departure_reason = employee.departure_reason_id.display_name or ""
            if employee.departure_description:
                departure_reason = f"{departure_reason}: {employee.departure_description}"
            return [
                employee.company_id.name or "", employee.company_id.l10n_eg_nosi_code or "",
                employee.l10n_eg_ssn or "", employee.identification_id or "", employee.name or "",
                employee.departure_date, departure_reason,
                employee.private_phone or "", employee.private_email or "", address,
            ]

        date_spec = {"num_format": "yyyy-mm-dd", "border": 1}
        column_formats = [None, None, None, None, None, date_spec, None, None, None, None]

        return self._export_nosi_form_generic(
            form_name="NOSI Form 6", file_name="NOSI_Form_6_Export.xlsx",
            company_mandatory_fields=company_fields, employee_mandatory_fields=employee_fields,
            headers=headers, data_mapper_func=data_mapper, column_formats=column_formats,
            extra_validation_func=extra_validation)
