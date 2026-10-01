# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from ..utils.urbanpiper_connector import UrbanPiperConnector
from ..utils.urbanpiper_translation import get_urbanpiper_translation


class ProductTemplateAttributeValue(models.Model):
    _inherit = 'product.template.attribute.value'

    urbanpiper_store_ids = fields.Many2many(
        'pos.urbanpiper.store',
        string='UrbanPiper Stores',
        help="Set the online food delivery stores for this product option to be sold.",
    )
    urbanpiper_meal_type = fields.Selection([
        ('1', 'Vegetarian'),
        ('2', 'Non-Vegetarian'),
        ('3', 'Eggetarian'),
        ('4', 'N/A')], string='Meal Type', required=True, default='4', help="Product attribute meal type i.e. Veg, Non-Veg, etc.")

    def _set_meal_type(self):
        for ptav in self:
            ptav.urbanpiper_meal_type = ptav.product_tmpl_id.urbanpiper_meal_type or '4'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.product_tmpl_id.urbanpiper_meal_type != '4':
                record._set_meal_type()
        return records

    def write(self, vals):
        if 'urbanpiper_store_ids' not in vals:
            return super().write(vals)
        prev_store_options = dict(self._read_group(
            domain=[('id', 'in', self.ids), ('urbanpiper_store_ids', '!=', False)],
            groupby=['urbanpiper_store_ids'],
            aggregates=['id:array_agg'],
        ))
        res = super().write(vals)
        new_store_options = dict(self._read_group(
            domain=[('id', 'in', self.ids), ('urbanpiper_store_ids', '!=', False)],
            groupby=['urbanpiper_store_ids'],
            aggregates=['id:array_agg'],
        ))
        # enable newly added options
        self.process_option_changes(new_store_options, prev_store_options, True)
        # disable removed options
        self.process_option_changes(prev_store_options, new_store_options, False)
        for ptav in self:
            for store in ptav.product_tmpl_id.urbanpiper_store_ids:
                if store not in ptav.product_tmpl_id.attribute_line_ids.product_template_value_ids.urbanpiper_store_ids:
                    ptav.product_tmpl_id.urbanpiper_store_ids -= store
            for store in ptav.urbanpiper_store_ids:
                if store not in ptav.product_tmpl_id.urbanpiper_store_ids:
                    ptav.product_tmpl_id.with_context(skip_product_config_update=True).urbanpiper_store_ids |= store
        return res

    def process_option_changes(self, source_dict, target_dict, enable):
        """Compare two mappings of (store → option_ids) and toggle newly changed options."""
        for store, option_ids in source_dict.items():
            # Find options present in `source` but not in the corresponding target set
            changed_ids = set(option_ids) - set(target_dict.get(store, []))
            synced_ids = set((store.urbanpiper_synced_json or {}).get('synced_option_ids', []))
            if options_to_toggle := list(synced_ids & changed_ids):
                UrbanPiperConnector(store).post_hub_option_toggle(options_to_toggle, enable)

    def _prepare_urbanpiper_data(self, store):
        """
        # Part of Menu Sync
        Prepare option (attribute value) data to be sent to UrbanPiper.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/add-update-menu
        """
        option_data = []
        for option in self:
            ptav_name_translations = option.product_attribute_value_id.get_field_translations('name')
            value_dict = {
                'ref_id': f'{option.product_tmpl_id.id}-{option.product_attribute_value_id.id}',
                'title': option.product_attribute_value_id.with_context(lang='en_US').name,
                'available': True,
                'opt_grp_ref_ids': [f'{option.product_tmpl_id.id}-{i}' for i in option.attribute_id.ids],
                'price': option.price_extra or option.product_attribute_value_id.default_extra_price,
                'food_type': option.urbanpiper_meal_type,
                'translations': get_urbanpiper_translation({'title': ptav_name_translations})
            }
            option_data.append(value_dict)
        return option_data
