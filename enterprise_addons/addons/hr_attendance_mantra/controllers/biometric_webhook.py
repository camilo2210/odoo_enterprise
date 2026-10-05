# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MantraBiometricWebhookController(http.Controller):

    @http.route(
        "/hr_attendance/biometric_webhook/mantra/<string:token>",
        auth="public",
        type="http",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def biometric_webhook(self, token, **kwargs):
        company = request.env["res.company"]._get_company_by_mantra_token("mantra_webhook_token", token)
        if not company:
            raise Forbidden("Invalid webhook token.")

        try:
            payload = request.get_json_data()
        except Exception:
            _logger.warning("Malformed Mantra webhook payload for company %s", company.name, exc_info=True)
            return request.make_json_response({"transStatus": []}, status=400)

        transactions = payload.get("trans") if isinstance(payload, dict) else None
        if not isinstance(transactions, list):
            return request.make_json_response({"transStatus": []}, status=400)

        BiometricEvent = request.env["hr.attendance.biometric.event"].sudo().with_company(company)
        vals_list = []
        response = []
        for transaction in transactions:
            if not isinstance(transaction, dict):
                response.append({"status": 0})
                continue
            txn_id = transaction["txnId"]
            punch_id = transaction["punchId"]
            txn_datetime = transaction["txnDateTime"]
            device_id = transaction["dvcId"]

            if None in (txn_id, punch_id) or not txn_datetime:
                response.append({"txnId": txn_id, "status": 0})
                continue

            try:
                punch_datetime = BiometricEvent._parse_local_datetime(company, txn_datetime)
            except Exception:  # noqa: BLE001
                response.append({"txnId": txn_id, "status": 0})
                _logger.warning(
                    "Dropping biometric event for employee %s (device %s): "
                    "could not parse datetime %r",
                    punch_id, device_id, txn_datetime,
                    exc_info=True,
                )
                continue

            vals_list.append({
                "company_id": company.id,
                "provider": "mantra",
                "transaction_id": txn_id,
                "punch_reference": f"Mantra:{device_id or ''}:{txn_id}",
                "employee_code": str(punch_id),
                "punch_datetime": punch_datetime,
                "device_id": str(device_id) if device_id not in (None, "") else False,
            })

            response.append({"txnId": txn_id, "status": 1})
        BiometricEvent._get_or_create_events(vals_list)
        return request.make_json_response({"transStatus": response})
