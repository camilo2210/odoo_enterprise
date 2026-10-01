# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def _get_light_group_xmlids(self):
        return (
            *super()._get_light_group_xmlids(),
            'planning.group_planning_user',
            'planning.group_field_service_allow_customer_report',
            'planning.group_field_service_allow_material',
            'planning.group_field_service_allow_customer_ratings',
            'planning.group_field_service_allow_geolocation',
            'planning.group_field_service_allow_quotations',
            'planning.group_field_service_hide_price',
            'planning.group_field_service_allow_equipment',
        )
