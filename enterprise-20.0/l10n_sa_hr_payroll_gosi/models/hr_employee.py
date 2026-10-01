from datetime import datetime
from itertools import chain
from odoo.tools.urls import urljoin as url_join

import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError

GOSI_EMPLOYEE_BATCH_SIZE = 20


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_sa_gosi_last_sync_datetime = fields.Datetime(
        string="Last GOSI Sync Date", groups="hr_payroll.group_hr_payroll_user", readonly=True,
    )
    l10n_sa_gosi_last_request_failed = fields.Boolean(
        string="Last GOSI Sync Failed", groups="hr_payroll.group_hr_payroll_user", readonly=True,
    )
    l10n_sa_gosi_api_is_available = fields.Boolean(
        related="company_id.l10n_sa_gosi_api_is_available", groups="hr_payroll.group_hr_payroll_user"
    )

    l10n_sa_employee_code = fields.Char(inverse="_inverse_l10n_sa_employee_code")

    # CRUD
    def write(self, vals):
        gosi_values_to_check = vals.keys() & ['wage', 'l10n_sa_housing_allowance', 'l10n_sa_other_allowances']
        for record in self:
            if self.env.company.country_id.code != 'SA':
                break
            old_gosi_values = {val: record[val] for val in gosi_values_to_check}
            if record.is_in_contract and any(old_gosi_values[val] != vals.get(val) for val in gosi_values_to_check):
                record.review_state = '2_to_review'
                record.activity_schedule(
                    activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                    summary=self.env._('GOSI wage update required for %(employee_name)s', employee_name=record.name),
                    note=self.env._("<p>The employee's GOSI contribution wage has been updated. Make sure to update the employee's contribution details on the GOSI platform using the <b>GOSI Wages Update Sheet</b> available in the <b>Reporting</b> section. Once the update is completed, or if no update is required, set the review status to <b>Reviewed</b></p>"),
                    user_id=record.current_version_id.hr_responsible_id.id or self.env.user.id,
                    technical_usage="l10n_sa_gosi_wage_update"
                )
        res = super().write(vals)
        if len(self) == 1 and vals.get('l10n_sa_employee_code'):  # We don't want to trigger the update for many records in cases like imports
            self._l10n_sa_gosi_write_employee_deductions()
        return res

    # Computes
    def _inverse_l10n_sa_employee_code(self):
        self.filtered(lambda rec: not rec.l10n_sa_employee_code).write({
            'l10n_sa_company_social_insurance_percentage': False,
            'l10n_sa_company_oh_insurance_percentage': False,
            'l10n_sa_company_unemployment_insurance_percentage': False,
            'l10n_sa_employee_social_insurance_percentage': False,
            'l10n_sa_employee_oh_insurance_percentage': False,
            'l10n_sa_employee_unemployment_insurance_percentage': False,
            'l10n_sa_gosi_last_request_failed': False,
        })

    # Model Methods
    @api.model
    def _cron_l10n_sa_gosi_update_employee(self):
        context_now = fields.Datetime.context_timestamp(self.env.user, fields.Datetime.now())
        today = datetime.combine(context_now, datetime.min.time())

        domain = fields.Domain([
            ("company_id.l10n_sa_gosi_api_mode", "=", "prod"),
            ("l10n_sa_employee_code", "!=", False),
            ("company_id.l10n_sa_gosi_api_is_available", "=", True),
            ("l10n_sa_gosi_last_request_failed", "=", False),
            "|",
            ("l10n_sa_gosi_last_sync_datetime", "<", today),
            ("l10n_sa_gosi_last_sync_datetime", "=", False),
        ])
        res = self.search(
            domain,
            order="l10n_sa_gosi_last_sync_datetime ASC NULLS FIRST",
        )

        access_token_dict = {}
        employee_batch = res[:GOSI_EMPLOYEE_BATCH_SIZE]
        remaining = len(res[GOSI_EMPLOYEE_BATCH_SIZE:])

        for employee in employee_batch:
            access_token = access_token_dict.get(employee.company_id.id)
            if not access_token:
                access_token = employee.company_id._l10n_sa_gosi_get_access_token()
                access_token_dict[employee.company_id.id] = access_token

            employee._l10n_sa_gosi_write_employee_deductions(access_token)

        if remaining:
            cron = self.env['ir.cron'].browse(self.env.context.get('cron_id'))
            cron and cron._commit_progress(len(employee_batch), remaining, remaining == 0)

    @api.model
    def _l10n_sa_gosi_get_coverage_fields_company(self) -> dict:
        """Returns the mappings between coverage & odoo fields"""
        return {
            "Annuity": {
                "employee": "l10n_sa_employee_social_insurance_percentage",
                "company": "l10n_sa_company_social_insurance_percentage",
            },
            "UI": {
                "employee": "l10n_sa_employee_unemployment_insurance_percentage",
                "company": "l10n_sa_company_unemployment_insurance_percentage",
            },
            "OH": {
                "employee": "l10n_sa_employee_oh_insurance_percentage",
                "company": "l10n_sa_company_oh_insurance_percentage",
            },
        }

    @api.model
    def _l10n_sa_gosi_prepare_write_vals(self, data: dict, set_empty_false=True) -> dict:
        coverage_mapping_dict = self._l10n_sa_gosi_get_coverage_fields_company()
        vals = {
            "l10n_sa_gosi_last_sync_datetime": fields.Datetime.now(),
            "l10n_sa_gosi_last_request_failed": False,
        }
        for coverage in data.get("engagement", {}).get("coverage", []):
            for field_key, value_key in [("employee", "employeeDeductionRate"), ("company", "employerDeductionRate")]:
                field_name = coverage_mapping_dict.get(coverage.get("code"), {}).get(field_key)
                value = coverage.get(value_key, 0) / 100
                if field_name:
                    vals.update({field_name: value})

        if set_empty_false:
            for coverage_field in chain.from_iterable(code.values() for code in coverage_mapping_dict.values()):
                vals.update({coverage_field: vals.get(coverage_field, 0)})
        return vals

    # Helpers
    def _l10n_sa_gosi_write_employee_deductions(self, access_token: str | bool = False) -> bool:
        self.ensure_one()
        if not (self.l10n_sa_employee_code and self.company_id.l10n_sa_gosi_api_is_available) or self.country_code != 'SA':
            return False

        res = self.sudo()._l10n_sa_gosi_get_employee_deductions(access_token)
        success = True
        if not res.get("engagement", {}).get("coverage"):
            vals = {"l10n_sa_gosi_last_request_failed": True}
            success = False
        else:
            vals = self._l10n_sa_gosi_prepare_write_vals(res)
        self.write(vals)
        return success

    def _l10n_sa_gosi_get_employee_deductions(self, access_token: str | bool = False) -> dict:
        self.ensure_one()
        data = {}
        try:
            url = url_join(
                self.company_id._l10n_sa_gosi_get_base_url(),
                f"/v2/establishment/{self.company_id.l10n_sa_gosi_registration_number}/contributor/{self.l10n_sa_employee_code}",
            )

            dpop = self.company_id.l10n_sa_gosi_dpop_private_key_id._l10n_sa_gosi_generate_dpop_jwt("GET", url)
            access_token = access_token or self.company_id._l10n_sa_gosi_get_access_token()
            if not access_token:
                return {}

            headers = {
                "x-apikey": self.company_id.l10n_sa_gosi_api_key,
                "dpop": dpop,
                "Authorization": f"Bearer {access_token}",
            }
            response = requests.request("GET", url, headers=headers, timeout=10)
            data = response.json()
            response.raise_for_status()
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout, ValueError, ValidationError):
            return {}
        return data
