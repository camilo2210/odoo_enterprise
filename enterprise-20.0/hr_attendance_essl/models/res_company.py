# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import api, fields, models
from odoo.tools.urls import urljoin
from odoo.tools import consteq


class ResCompany(models.Model):
    _inherit = "res.company"

    essl_webhook_token = fields.Char(
        copy=False,
        groups="hr_attendance.group_hr_attendance_manager",
        default=lambda self: uuid.uuid4().hex,
    )
    essl_webhook_url = fields.Char(compute="_compute_essl_webhook_url")

    @api.model
    def _get_company_by_essl_token(self, token_field, token):
        if not token:
            return self

        companies = self.sudo().search([(token_field, "!=", False)])
        for company in companies:
            if consteq(company[token_field], token):
                return company
        return self

    def _compute_essl_webhook_url(self):
        base_url = self.env["res.company"].get_base_url()
        for company in self:
            company.essl_webhook_url = company.essl_webhook_token and urljoin(
                base_url,
                f"/hr_attendance/biometric_webhook/essl/{company.essl_webhook_token}",
            )

    def action_regenerate_essl_webhook_token(self):
        self.ensure_one()
        self.write({"essl_webhook_token": uuid.uuid4().hex})
