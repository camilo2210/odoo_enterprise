# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class WorksheetTemplate(models.Model):
    _inherit = 'worksheet.template'

    @api.model
    def _get_models_to_check_dict(self):
        res = super()._get_models_to_check_dict()
        res['maintenance.request'] = [('maintenance.request', 'Maintenance Request')]
        return res
