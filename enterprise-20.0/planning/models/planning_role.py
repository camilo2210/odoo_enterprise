# Part of Odoo. See LICENSE file for full copyright and licensing details.
from random import randint

from odoo import fields, models


class PlanningRole(models.Model):
    _name = 'planning.role'
    _description = "Planning Role"
    _order = 'sequence'
    _rec_name = 'name'

    def _get_default_color(self):
        return randint(1, 11)

    active = fields.Boolean('Active', default=True)
    name = fields.Char('Name', required=True, translate=True)
    color = fields.Integer("Color", default=_get_default_color)
    resource_ids = fields.Many2many('resource.resource', 'resource_resource_planning_role_rel',
                                    'planning_role_id', 'resource_resource_id', 'Resources')
    sequence = fields.Integer(export_string_translation=False)
    slot_properties_definition = fields.PropertiesDefinition('Planning Slot Properties')
