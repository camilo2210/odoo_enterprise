# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ReportQuality_ControlQuality_Worksheet(models.AbstractModel):
    _inherit = "report.quality_control.quality_worksheet"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['quality.check'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'quality.check',
            'docs': docs,
        }
