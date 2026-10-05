# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, api, fields, models

from odoo.tools import html2plaintext

from ..utils.urbanpiper_translation import get_urbanpiper_translation
from ..utils.urbanpiper_image_url import get_urbanpiper_image_url
from ..utils.urbanpiper_connector import UrbanPiperConnector


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    urbanpiper_store_ids = fields.Many2many(
        'pos.urbanpiper.store',
        string='UrbanPiper Stores',
        help="Set the online food delivery stores for this product to be sold.",
    )
    allowed_delivery_provider_ids = fields.Many2many(
        string='Allowed Delivery Aggregators',
        related='urbanpiper_store_ids.delivery_provider_ids',
    )
    urbanpiper_pos_platform_ids = fields.Many2many(
        'pos.delivery.provider',
        string='Aggregators',
        compute='_compute_urbanpiper_pos_platforms',
        domain="[('id', 'in', allowed_delivery_provider_ids)]",
        store=True,
        readonly=False,
        compute_sudo=True,
        help="Select the online food delivery platforms on which this product will be available.",
    )
    urbanpiper_meal_type = fields.Selection([
        ('1', 'Vegetarian'),
        ('2', 'Non-Vegetarian'),
        ('3', 'Eggetarian'),
        ('4', 'N/A')], string='Meal Type', required=True, default='4', help="Product type i.e. Veg, Non-Veg, etc.")
    is_alcoholic_on_urbanpiper = fields.Boolean(string='Is Alcoholic', help="Indicates if the product contains alcohol.")
    is_recommended_on_urbanpiper = fields.Boolean(string='Is Recommended', help="Recommended products on food platforms.")

    @api.depends('urbanpiper_store_ids')
    def _compute_urbanpiper_pos_platforms(self):
        for record in self:
            record.urbanpiper_pos_platform_ids = [Command.set(record.urbanpiper_store_ids.delivery_provider_ids.ids)]

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['urbanpiper_store_ids']

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if not config.module_pos_urban_piper:
            return read_records
        synced_product_ids = (config.urbanpiper_store_id.urbanpiper_synced_json or {}).get('synced_product_ids', [])
        for product in read_records:
            product['_synced_on_urbanpiper'] = product['id'] in synced_product_ids
        return read_records

    def write(self, vals):
        skip_urbanpiper_item_sync = 'urbanpiper_store_ids' not in vals or self.env.context.get('from_pos_ui')
        prev_store_products = dict(self._read_group(
            domain=[('id', 'in', self.ids), ('urbanpiper_store_ids', '!=', False)],
            groupby=['urbanpiper_store_ids'],
            aggregates=['id:array_agg'],
        )) if not skip_urbanpiper_item_sync else {}

        res = super().write(vals)
        if 'urbanpiper_meal_type' in vals:
            self.attribute_line_ids.product_template_value_ids.filtered(lambda ptav: ptav.ptav_active)._set_meal_type()
        if skip_urbanpiper_item_sync:
            return res

        new_store_products = dict(self._read_group(
            domain=[('id', 'in', self.ids), ('urbanpiper_store_ids', '!=', False)],
            groupby=['urbanpiper_store_ids'],
            aggregates=['id:array_agg'],
        ))
        # enable newly added products
        self._process_changes(new_store_products, prev_store_products, True)
        # disable removed products
        self._process_changes(prev_store_products, new_store_products, False)

        if not self.env.context.get('skip_product_config_update'):
            for product in self:
                product.attribute_line_ids.product_template_value_ids.urbanpiper_store_ids = product.urbanpiper_store_ids
        return res

    def _process_changes(self, source_dict, target_dict, status):
        """Compare two mappings of (store → product_ids) and toggle newly changed products."""
        for store, product_ids in source_dict.items():
            # Find items present in `source` but not in the corresponding target set
            changed_ids = set(product_ids) - set(target_dict.get(store, []))
            synced_ids = set((store.urbanpiper_synced_json or {}).get('synced_product_ids', []))
            if products_to_toggle := list(synced_ids & changed_ids):
                UrbanPiperConnector(store).post_hub_item_toggle(products_to_toggle, status)

    def _get_urbanpiper_unit_price(self, urbanpiper_store):
        """Return the product's unit price for UrbanPiper menu synchronization.

        By default, this uses the product's sales price. Localizations may override
        this to compute the price from a store-specific pricelist.
        """
        return self.list_price

    def _prepare_urbanpiper_data(self, urbanpiper_store):
        """
        # Part of Menu Sync
        Prepare items data to be sent on UrbanPiper for menu sync.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/add-update-menu
        """
        data = []

        for product in self:
            company_domain = self.env['account.tax']._check_company_domain(urbanpiper_store.company_id)
            company_taxes = product.taxes_id.filtered_domain(company_domain)
            product_price = product._get_urbanpiper_unit_price(urbanpiper_store)
            price_after_tax_tag = company_taxes.compute_all(product_price, product.currency_id)[urbanpiper_store.tax_type]

            platforms = [prov.technical_name for prov in (product.urbanpiper_pos_platform_ids & urbanpiper_store.delivery_provider_ids)]
            name_translations = product.get_field_translations('name')
            description_translations = product.get_field_translations('public_description')
            item = {
                'tags': product._prepare_urbanpiper_product_tags(urbanpiper_store),
                'ref_id': str(product.id),
                'title': product.with_context(lang='en_US').name,
                'description': html2plaintext(product.with_context(lang='en_US').public_description) if product.public_description else '',
                'price': price_after_tax_tag,
                'weight': product.weight,
                'food_type': product.urbanpiper_meal_type,
                'category_ref_ids': [str(i) for i in product.pos_categ_ids.ids] if product.pos_categ_ids else ['0'],  # '0' means 'Other' category
                'recommended': product.is_recommended_on_urbanpiper,
                'available': True,
                'included_platforms': (platforms),
                'translations': get_urbanpiper_translation({
                    'title': name_translations,
                    'description': description_translations,
                }),
                'platform_pricing': product._prepare_urbanpiper_platform_pricing(urbanpiper_store, company_taxes),
            }
            if img_url := get_urbanpiper_image_url(urbanpiper_store, product):
                item['img_url'] = img_url
            data.append(item)

        return data

    def _prepare_urbanpiper_platform_pricing(self, urbanpiper_store, company_taxes):
        """
        Prepare platform-specific pricing for a product using store aggregators.
        Computes the product price from each aggregator's pricelist (if set),
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/add-update-menu#sample-curl:~:text=values%20of%20platforms-,platform_pricing,-array%5Bobject%5D
        """
        self.ensure_one()
        platform_pricing = []
        base_pricelist = urbanpiper_store.preset_id.pricelist_id

        for aggregator in urbanpiper_store.aggregator_lines:
            pricelist = aggregator.sudo().pricelist_id
            if (
                pricelist
                and pricelist != base_pricelist
                and pricelist.filtered_domain(pricelist._check_company_domain(urbanpiper_store.company_id))
            ):
                price = pricelist.with_company(urbanpiper_store.company_id)._get_product_price(self, 1.0, uom=self.uom_id)
                platform_pricing.append({
                    'platform': aggregator.delivery_provider_id.technical_name,
                    'price': company_taxes.compute_all(price, self.currency_id, 1)[urbanpiper_store.tax_type],
                })
        return platform_pricing

    def _prepare_urbanpiper_product_tags(self, urbanpiper_store):
        """Prepare UrbanPiper product tags to include with item data sent to UrbanPiper."""
        self.ensure_one()
        tags = {}
        default_tags = []
        for product_tag in self.product_tag_ids:
            default_tags.append(product_tag.name)
        tags['default'] = default_tags
        for provider in (self.urbanpiper_pos_platform_ids & urbanpiper_store.delivery_provider_ids):
            tags[provider.technical_name] = [
                'alcohol-present' if self.is_alcoholic_on_urbanpiper else 'alcohol-absent', *default_tags
            ]
        return tags

    def _prepare_urbanpiper_option_groups_data(self, store):
        """
        # Part of Menu Sync
        Prepare option groups (attribute line) data to be sent to UrbanPiper.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/add-update-menu
        """
        option_groups_data = []
        has_doordash = any(p.technical_name == 'doordash' for p in store.delivery_provider_ids)

        for product in self:
            for attr_line in product.attribute_line_ids:
                attr_name_translations = attr_line.attribute_id.get_field_translations('name')
                group = {
                    'ref_id': f'{product.id}-{attr_line.attribute_id.id}',
                    'title': attr_line.attribute_id.with_context(lang='en_US').name,
                    'active': True,
                    'multi_options_enabled': attr_line.is_urbanpiper_multi_modifiers,
                    'item_ref_ids': [str(product.id)],
                    'translations': get_urbanpiper_translation({'title': attr_name_translations}),
                }
                if attr_line.attribute_id.display_type != 'multi':
                    group['min_selectable'] = 1
                    group['max_selectable'] = 1
                else:
                    max_selectable = 30 if attr_line.urbanpiper_max_qty == -1 and has_doordash else attr_line.urbanpiper_max_qty
                    group['max_selectable'] = max_selectable
                    group['min_selectable'] = min(attr_line.urbanpiper_min_qty, max_selectable)
                option_groups_data.append(group)
        return option_groups_data

    def _prepare_urbanpiper_charges_data(self, urbanpiper_store):
        """
        # Part of Menu Sync
        Prepare charge data (e.g., packaging, delivery) for UrbanPiper menu sync.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/add-update-menu#:~:text=in%20the%20array.-,Charges,-Array%20of%20Charge
        """
        product_packaging = self.env.ref('pos_urban_piper.product_packaging_charges', False)
        product_delivery = self.env.ref('pos_urban_piper.product_delivery_charges', False)

        charges_data = []
        for product in [product_packaging, product_delivery]:
            if product and product.list_price > 0:
                charges_data.append({
                    'code': 'PC_F' if product.id == product_packaging.id else 'DC_F',
                    'title': product.with_context(lang='en_US').name,
                    'active': True,
                    'item_ref_ids': ['all'],
                    'structure': {
                        'applicable_on': 'order.order_subtotal',
                        'value': product.list_price
                    },
                })

        return charges_data

    def _prepare_urbanpiper_taxes_data(self, urbanpiper_store):
        """
        # Part of Menu Sync
        Prepare tax data for UrbanPiper menu sync based on given products.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/add-update-menu#:~:text=suggest%20any%20changes.-,Taxes,-Array%20of%20Tax
        """
        if urbanpiper_store.tax_type == 'total_included':
            return []
        taxes_data = []
        for parent_tax, product_ids in self._read_group(
            [('id', 'in', self.ids)],
            groupby=['taxes_id'],
            aggregates=['id:array_agg'],
        ):
            if parent_tax.type_tax_use != 'sale':
                continue
            company_domain = self.env['account.tax']._check_company_domain(urbanpiper_store.company_id)
            for tax in parent_tax.flatten_taxes_hierarchy().filtered_domain(company_domain):
                if tax_data := tax._prepare_urbanpiper_data(urbanpiper_store, product_ids):
                    taxes_data.append(tax_data)
        return taxes_data

    def toggle_product_food_delivery_availability(self, store_id):
        """ Toggle a product's availability on the UrbanPiper."""
        self.ensure_one()
        new_status = store_id not in self.urbanpiper_store_ids.ids
        store = self.env['pos.urbanpiper.store'].browse(store_id).exists()
        up = UrbanPiperConnector(store)
        toggle_response = up.post_hub_item_toggle(self.ids, new_status)
        if toggle_response.get('status') != 'success':
            return {
                'status': toggle_response.get('status'),
                'error': next(iter(toggle_response.get('errors', {}).values()), '')
            }
        if new_status:
            self.urbanpiper_store_ids |= store
        else:
            self.urbanpiper_store_ids -= store
        return toggle_response
