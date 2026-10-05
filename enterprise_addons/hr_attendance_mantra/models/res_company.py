# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import api, fields, models
from odoo.tools.urls import urljoin
from odoo.tools import consteq


class ResCompany(models.Model):
    _inherit = "res.company"

    mantra_webhook_token = fields.Char(
        copy=False,
        groups="hr_attendance.group_hr_attendance_manager",
        default=lambda self: uuid.uuid4().hex,
    )
    mantra_webhook_url = fields.Char(compute="_compute_mantra_webhook_url")

    @api.model
    def _get_company_by_mantra_token(self, token_field, token):
        if not token:
            return self.browse()

        companies = self.sudo().search([(token_field, "!=", False)])
        for company in companies:
            if consteq(company[token_field], token):
                return company
        return self.browse()

    def _compute_mantra_webhook_url(self):
        base_url = self.env["res.company"].get_base_url()
        for company in self:
            company.mantra_webhook_url = company.mantra_webhook_token and urljoin(
                base_url,
                f"/hr_attendance/biometric_webhook/mantra/{company.mantra_webhook_token}",
            )

    def action_regenerate_mantra_webhook_token(self):
        self.ensure_one()
        self.write({"mantra_webhook_token": uuid.uuid4().hex})
