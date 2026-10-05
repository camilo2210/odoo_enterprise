from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

_POST_INTERVENTION_WATCH_TIMEOUT = 1


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def update_resource_live_location(self, latitude, longitude):
        resource = self.env.user.employee_id.resource_id  # only update current company's resource live location
        if not (
            resource and
            self.env['res.groups']._is_feature_enabled('planning.group_field_service_allow_geolocation') and
            self.env.user.has_group("planning.group_planning_user")
        ):
            return False

        if self.should_erase_live_location():
            self.erase_resource_live_location()
            return False

        return resource.sudo().write({
            'live_latitude': latitude,
            'live_longitude': longitude,
            'live_location_last_update': fields.Datetime.now(),
        })

    @api.model
    def should_erase_live_location(self):
        resource = self.env.user.employee_id.resource_id

        now = fields.Datetime.now()
        current_slot = self.env['planning.slot'].sudo().search(
            domain=[
                ('start_datetime', '<=', now),
                ('end_datetime', '>=', now),
                ('resource_ids', 'in', resource.ids),
            ],
        )
        if current_slot:
            return False

        today = fields.Datetime.today()
        last_slot_of_the_day = self.env['planning.slot'].sudo().search(
            domain=[
                ('start_datetime', '>=', today),
                ('end_datetime', '<', today + relativedelta(days=1)),
                ('resource_ids', 'in', resource.ids),
            ],
            order='end_datetime desc',
            limit=1,
        )
        return (
            not last_slot_of_the_day or
            now > last_slot_of_the_day.end_datetime + relativedelta(hours=_POST_INTERVENTION_WATCH_TIMEOUT)
        )

    @api.model
    def erase_resource_live_location(self):
        resource = self.env.user.employee_id.resource_id
        resource.sudo()._erase_resource_live_location()
