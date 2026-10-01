# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from werkzeug.exceptions import Forbidden


from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EsslBiometricWebhookController(http.Controller):

    @http.route(
        "/hr_attendance/biometric_webhook/essl/<string:token>",
        auth="public",
        type="http",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def biometric_webhook(self, token, **kwargs):
        company = request.env["res.company"]._get_company_by_essl_token("essl_webhook_token", token)
        if not company:
            raise Forbidden("Invalid webhook token.")

        try:
            payload = request.get_json_data()
        except Exception:
            _logger.warning("Malformed eSSL webhook payload for company %s", company.name, exc_info=True)
            return request.make_json_response([], status=400)

        records = payload if isinstance(payload, list) else payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            return request.make_json_response([], status=400)

        BiometricEvent = request.env["hr.attendance.biometric.event"].sudo().with_company(company)
        vals_list = []
        response = []

        for record in records:
            if not isinstance(record, dict):
                response.append({"status": 0})
                continue

            employee_code = record["EmployeeCode"]
            log_date = record["LogDate"]
            serial_number = record["SerialNumber"]

            if not (employee_code and log_date and serial_number):
                response.append({"EmployeeCode": employee_code, "LogDate": log_date, "status": 0})
                continue

            try:
                punch_datetime = BiometricEvent._parse_local_datetime(company, log_date)
            except Exception:  # noqa: BLE001
                _logger.warning(
                    "Dropping biometric event for employee %s (serial %s): "
                    "could not parse LogDate %r",
                    employee_code, serial_number, log_date,
                    exc_info=True,
                )
                response.append({"EmployeeCode": employee_code, "LogDate": log_date, "status": 0})
                continue

            vals_list.append({
                "company_id": company.id,
                "provider": "essl",
                "punch_reference": f"ESSL:{serial_number or ''}:{employee_code or ''}:{log_date or ''}",
                "employee_code": str(employee_code),
                "punch_datetime": punch_datetime,
                "device_id": str(serial_number),
            })

            response.append({"EmployeeCode": employee_code, "LogDate": log_date, "status": 1})

        if vals_list:
            results = BiometricEvent._get_or_create_events(vals_list)
            _logger.info("eSSL webhook results for company %s: %s", company.name, results)

        return request.make_json_response(response)
