from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class ResourceResource(models.Model):
    _inherit = 'resource.resource'

    live_latitude = fields.Float(digits=(10, 7), readonly=True)
    live_longitude = fields.Float(digits=(10, 7), readonly=True)
    live_location_last_update = fields.Datetime(readonly=True)

    def _get_work_location(self, company=None):
        return self.mapped(lambda r: r.employee_id.address_id or (company or r.company_id).partner_id)

    def _erase_resource_live_location(self):
        self.live_latitude = False
        self.live_longitude = False
        self.live_location_last_update = False

    @api.model
    def _cron_remove_outdated_live_location(self):
        now = fields.Datetime.now()
        delta = relativedelta(days=1)
        resources = self.env['resource.resource'].search([('live_location_last_update', '<=', now - delta)])
        resources._erase_resource_live_location()
