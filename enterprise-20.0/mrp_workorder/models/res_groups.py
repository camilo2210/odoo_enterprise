# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def _get_light_group_xmlids(self):
        return (
            *super()._get_light_group_xmlids(),
            'mrp_workorder.group_mrp_wo_tablet_timer',
            'mrp_workorder.group_mrp_wo_shop_floor',
        )
