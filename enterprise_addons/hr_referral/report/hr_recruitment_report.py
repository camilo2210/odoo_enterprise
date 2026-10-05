# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import SQL


class HrRecruitmentReport(models.Model):
    _inherit = "hr.recruitment.report"

    has_referrer = fields.Integer(aggregator="sum", readonly=True)
    referral_hired = fields.Integer('# Hired by Referral', aggregator="sum", readonly=True)

    def _query(self, fields=SQL(), from_clause=SQL()):
        return super()._query(SQL("""%s
            , CASE WHEN a.ref_user_id IS NOT NULL THEN 1 ELSE 0 END as has_referrer,
            CASE WHEN a.date_closed IS NOT NULL AND a.ref_user_id IS NOT NULL THEN 1 ELSE 0 END as referral_hired
            """, fields
        ), from_clause)
