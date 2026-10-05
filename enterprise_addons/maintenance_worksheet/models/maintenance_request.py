# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    worksheet_template_id = fields.Many2one(
        'worksheet.template', index='btree_not_null',
        domain="[('res_model', '=', 'maintenance.request'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Create templates for each type of request you have and customize their content with your own custom fields.")

    worksheet_properties = fields.Properties('Worksheet Properties', definition='worksheet_template_id.worksheet_properties_definition', copy=True)
    currency_id = fields.Many2one('res.currency', related='worksheet_template_id.currency_id')

    def _get_props_formatted(self):
        for maintenance_request in self:
            if maintenance_request.worksheet_properties:
                properties_values = maintenance_request.worksheet_properties.field.convert_to_read(
                    maintenance_request.worksheet_properties._values,
                    maintenance_request.worksheet_properties.record,
                    use_display_name=False,
                )
                for prop in properties_values:
                    if prop['type'] == 'monetary':
                        prop['currency_field'] = self.currency_id
                return maintenance_request.worksheet_template_id.format_props(properties_values)
        return []
