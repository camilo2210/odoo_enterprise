# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools import SQL


class MailingTraceReport(models.Model):
    _inherit = 'mailing.trace.report'

    def _report_get_request_where_items(self):
        res = super()._report_get_request_where_items()
        res.append(SQL("mailing.use_in_marketing_automation IS NOT TRUE"))
        return res
