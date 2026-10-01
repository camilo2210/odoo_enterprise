# Part of Odoo. See LICENSE file for full copyright and licensing details
import logging
import traceback
from itertools import batched, islice

from psycopg2.errors import SerializationFailure

from odoo import _, fields, models
from odoo.tools import BinaryBytes

from odoo.addons.website_sale.const import SNIPPET_DEFAULTS

logger = logging.getLogger(__name__)

CATEGORIES_BATCH_SIZE = 10
PRODUCTS_BATCH_SIZE = 5
PROGRESS_BASIS = 10000  # Large basis in order to see integer progress for large number of products
MAX_PRODUCT_FAIL_REPORT = 10
WEIGHT_PROGRESS_CATEGORY = 1
WEIGHT_PROGRESS_PRODUCT = 10
PROGRESS_CATEGORY_TOTAL = (WEIGHT_PROGRESS_CATEGORY / (WEIGHT_PROGRESS_CATEGORY + WEIGHT_PROGRESS_PRODUCT))
PROGRESS_PRODUCT_TOTAL = (WEIGHT_PROGRESS_PRODUCT / (WEIGHT_PROGRESS_CATEGORY + WEIGHT_PROGRESS_PRODUCT))
DYNAMIC_VARIANT_LIMIT = 100000


class Website_GeneratorRequest(models.Model):
    _inherit = 'website_generator.request'

    import_products = fields.Boolean(string="Import Products", default=False)
    ecommerce_platform = fields.Char(string="eCommerce Platform of the website to import", default='auto')

    def _get_call_params(self):
        data = super()._get_call_params()
        data['import_products'] = self.import_products
        data['ecommerce_platform'] = self.ecommerce_platform
        return data

    def _generation_progress_init(self):
        generation_progress = super()._generation_progress_init()
        generation_progress.update({
            'category_id_map': {},
            'last_product_id': 0,
            'last_category_id': 0,
            'n_report_iap_products': 0,
            'initial_variant_limit': None,
        })
        return generation_progress

    def _apply_html_replacements(self, body_html, pattern_sorted_html, direct_replacement_mapping, image_replacement_mapping, template_key_to_filter_xmlid=None):
        template_key_to_filter_xmlid = template_key_to_filter_xmlid or {}
        template_key_to_filter_xmlid.update({
            v['template_key']: v['filter_xmlid']
            for v in SNIPPET_DEFAULTS.values()
            if 'template_key' in v and 'filter_xmlid' in v
        })
        return super()._apply_html_replacements(body_html, pattern_sorted_html, direct_replacement_mapping, image_replacement_mapping, template_key_to_filter_xmlid)

    def _create_products(self, request_index, total_requests, odoo_blocks, generation_progress):
        if not self.import_products:
            return 0

        # Increase the maximum number of variants
        ICP = self.env['ir.config_parameter'].sudo()
        if not generation_progress.get('initial_variant_limit'):
            generation_progress['initial_variant_limit'] = ICP.get_int('product.dynamic_variant_limit')

        # Set the variant setting so that they can see the variants that we create
        if not generation_progress.get('turned_on_variants'):
            self.env['res.config.settings'].sudo().create({
                'group_product_variant': True,
            }).execute()
            generation_progress['turned_on_variants'] = True

        ICP.set_int('product.dynamic_variant_limit', DYNAMIC_VARIANT_LIMIT)

        # Generate all the categories and products
        start_progress = request_index * PROGRESS_BASIS
        total_progress = PROGRESS_BASIS * total_requests
        all_product_images = odoo_blocks['website'].get('all_product_images', {})
        categories = odoo_blocks.get('categories', {})
        products = odoo_blocks.get('products', {})

        # Create public categories
        last_category_id = generation_progress['last_category_id']
        for batch_category_data in batched(islice(categories.items(), last_category_id, None), CATEGORIES_BATCH_SIZE):
            try:
                # Create batch of categories
                batch_category_vals = [{'name': category[1].get('name'), 'website_id': self.website_id.id} for category in batch_category_data]
                category_records = self.env['product.public.category'].sudo().create(batch_category_vals)

                # Add images and store redirects in memory
                for (category_record, (path, category_data)) in zip(category_records, batch_category_data):
                    generation_progress['direct_html_replacements_mapping'][path] = f'/shop/category/{self.env["ir.http"]._slug(category_record)}'
                    generation_progress['category_id_map'][category_data['id']] = category_record.id
                    images = [category_data.get('image', '')]
                    images_info = self._get_image_info(images, all_product_images, generation_progress)
                    if images_info:
                        category_record.image_1920 = BinaryBytes(images_info[0]['raw'])
                        category_record.cover_image = BinaryBytes(images_info[0]['raw'])

                # Save progress
                generation_progress['last_category_id'] = min(len(categories), generation_progress['last_category_id'] + CATEGORIES_BATCH_SIZE)
                self.generation_progress = generation_progress
                current_progress = int(start_progress + PROGRESS_CATEGORY_TOTAL * (generation_progress['last_category_id'] / len(categories)) * PROGRESS_BASIS)
                processed = int(PROGRESS_CATEGORY_TOTAL * (len(batch_category_data) / len(categories)) * PROGRESS_BASIS)
                logger.info("Request %s/%s, Importing categories: %s/%s", request_index + 1, total_requests, generation_progress['last_category_id'], len(categories))
                self.env['ir.cron']._commit_progress(processed=processed, remaining=total_progress - current_progress)
            except SerializationFailure:
                # Here to re-trigger the cron in case of SerializationFailure
                raise
            except Exception:
                self.env['ir.cron']._rollback_progress()
                logger.exception("Error importing categories")
                self._report_product_fail()
                generation_progress['last_category_id'] = min(len(categories), generation_progress['last_category_id'] + CATEGORIES_BATCH_SIZE)

        # Set the progress to complete for categories
        start_progress += (WEIGHT_PROGRESS_CATEGORY / (WEIGHT_PROGRESS_CATEGORY + WEIGHT_PROGRESS_PRODUCT)) * PROGRESS_BASIS

        # Create products
        last_product_id = generation_progress['last_product_id']
        for batch_product_data in batched(islice(products.items(), last_product_id, None), PRODUCTS_BATCH_SIZE):
            try:
                # Create batch of products
                batch_product_vals = []
                for (__, product_data) in batch_product_data:
                    product_vals = {
                        'name': product_data.get('name'),
                        'list_price': product_data.get('price'),
                        'website_published': product_data.get('website_published', True),
                        'description_ecommerce': product_data.get('description', ''),
                        'website_id': self.website_id.id,
                    }

                    if product_data.get('default_code'):
                        product_vals['default_code'] = product_data.get('default_code')

                    # Link product category and create it if needed
                    # Note: product category != public category
                    if product_category := product_data.get('category'):
                        category = self._get_or_create(
                            self.env['product.category'],
                            domain=[('name', '=', product_category)],
                            vals={'name': product_category},
                        )
                        product_vals['categ_id'] = category.id
                    batch_product_vals.append(product_vals)
                products_record = self.env['product.template'].sudo().create(batch_product_vals)

                # Add images and store redirects in memory
                redirect_vals = []
                for (product_record, (path, product_data)) in zip(products_record, batch_product_data):
                    generation_progress['direct_html_replacements_mapping'][path] = product_record.website_url
                    # A redirect to itself is invalid and unnecessary.
                    if path != product_record.website_url:
                        redirect_vals.append({
                            'name': _("Redirect to %(product_name)s", product_name=product_record.name),
                            'website_id': self.website_id.id,
                            'url_from': path,
                            'url_to': product_record.website_url,
                            'redirect_type': '301',
                        })
                    images = product_data.get('images', [])
                    images_info = self._get_image_info(images, all_product_images, generation_progress)
                    if not images_info:
                        logger.warning('Warning creating product: product %s has no images.', product_data.get('name'))
                        continue

                    # Create product images
                    product_record.image_1920 = images_info[0]['raw']
                    product_images = [{
                        'name': image_info['name'],
                        'image_1920': image_info['raw'],
                        'product_tmpl_id': product_record.id,
                    } for image_info in images_info[1:]]
                    self.env['product.image'].sudo().create(product_images)

                # Add redirects to maintain SEO
                if redirect_vals:
                    self.env['website.rewrite'].sudo().create(redirect_vals)

                # Add public categories and variants
                for (product_record, (path, product_data)) in zip(products_record, batch_product_data):
                    # Link public categories
                    public_categ_ids = [
                        generation_progress['category_id_map'][imported_id]
                        for imported_id in product_data.get('public_category_ids', [])
                        if imported_id in generation_progress['category_id_map']
                    ]
                    product_record.write({
                        'public_categ_ids': public_categ_ids,
                    })

                    # Add variants
                    all_variant_image_vals = self._manage_attributes(product_data, product_record, all_product_images, generation_progress)
                    self.env['product.image'].sudo().create(all_variant_image_vals)

                # Save progress
                generation_progress['last_product_id'] = min(len(products), generation_progress['last_product_id'] + PRODUCTS_BATCH_SIZE)
                self.generation_progress = generation_progress
                current_progress = int(start_progress + PROGRESS_PRODUCT_TOTAL * (generation_progress['last_product_id'] / len(products)) * PROGRESS_BASIS)
                processed = int(PROGRESS_PRODUCT_TOTAL * (len(batch_product_data) / len(products)) * PROGRESS_BASIS)
                logger.info("Request %s/%s, Importing products: %s/%s", request_index + 1, total_requests, generation_progress['last_product_id'], len(products))
                self.env['ir.cron']._commit_progress(processed=processed, remaining=total_progress - current_progress)
            except SerializationFailure:
                # Here to re-trigger the cron in case of SerializationFailure
                raise
            except Exception:
                self.env['ir.cron']._rollback_progress()
                logger.exception("Error importing products")
                self._report_product_fail()
                generation_progress['last_product_id'] = min(len(products), generation_progress['last_product_id'] + PRODUCTS_BATCH_SIZE)

        # Restore the maximum number of variants
        ICP.set_int('product.dynamic_variant_limit', generation_progress['initial_variant_limit'])
        return len(products)

    def _manage_attributes(self, product_data, product, all_product_images, generation_progress):
        attributes_values = product_data.get('attributes_values', {})
        cover_variant = product_data.get('cover_variant', '')
        cover_variant_values = set(cover_variant.split(' / ')) if cover_variant else set()
        total_combinations = 1
        # Parse the available combinations
        for attribute_name, unique_values in attributes_values.items():
            # Avoid creating attributes with no values
            if not attribute_name:
                continue
            total_combinations *= len(unique_values)
            if total_combinations > 10000:
                break
            # Find or create the attribute
            attribute = self._get_or_create(
                self.env['product.attribute'],
                domain=[('name', '=', attribute_name)],
                vals={'name': attribute_name},
            )

            # Find/create all the attribute values
            attribute_values = []
            for attr_value in unique_values:
                attribute_value = self._get_or_create(
                    self.env['product.attribute.value'],
                    domain=[('name', '=', attr_value), ('attribute_id', '=', attribute.id)],
                    vals={'name': attr_value, 'attribute_id': attribute.id},
                )
                attribute_values.append(attribute_value.id)

            # Create the product_attribute_line
            self.env['product.template.attribute.line'].sudo().create({
                'attribute_id': attribute.id,
                'product_tmpl_id': product.id,
                'value_ids': attribute_values,
            })

        # Make this variant show first to match the external website
        if cover_variant_values:
            for ptal in product.valid_product_template_attribute_line_ids:
                for sequence, ptav in enumerate(
                    sorted(ptal.product_template_value_ids, key=lambda v: v.name not in cover_variant_values),
                    start=1,
                ):
                    ptav.sequence = sequence

        # Set the attributes on the variants such as images and sku values
        # Disable all variants that are not actually on the original website
        variant_default_codes = product_data.get('variant_default_codes', {})
        variant_images = product_data.get('variant_images', {})
        all_variant_image_vals = []
        variants_to_remove = self.env['product.product']

        # This implies that there are no variants.
        if product.product_variant_count in [0, 1]:
            return all_variant_image_vals

        for variant in product.product_variant_ids:
            variant_names = variant.product_template_attribute_value_ids.mapped('name')
            variant_name = ' / '.join(sorted(variant_names))

            # If the variant did not exist on the api, we disable the variant
            if variant_name not in variant_default_codes:
                variants_to_remove += variant
                continue

            # Even though the variant may exist, sometimes the SKU value is actually empty
            default_code = variant_default_codes.get(variant_name)
            if default_code:
                variant.write({'default_code': default_code})

            images = variant_images.get(variant_name, [])
            images_info = self._get_image_info(images, all_product_images, generation_progress)
            if not images_info:
                continue
            variant.image_variant_1920 = images_info[0]['raw']
            all_variant_image_vals.extend({
                'name': image_info['name'],
                'image_1920': image_info['raw'],
                'product_variant_id': variant.id,
            } for image_info in images_info[1:])

        if variants_to_remove:
            variants_to_remove._unlink_or_archive()

        return all_variant_image_vals

    def _get_image_info(self, images, image_file_mappings, generation_progress):
        all_images_info = []
        filenames = []
        for image in images:
            image_filename = image_file_mappings.get(image)
            if not image_filename:
                continue
            filenames.append(image_filename)

        att_map = self._get_wg_attachment(filenames, generation_progress, reuse=True)
        for image_filename, att in att_map.items():
            all_images_info.append({
                'name': image_filename,
                'raw': att.raw,
            })
        return all_images_info

    @staticmethod
    def _get_or_create(recordset, domain, vals):
        record = recordset.sudo().search(domain, limit=1)
        return record if record else recordset.sudo().create(vals)

    def _report_product_fail(self):
        generation_progress = self.generation_progress
        if generation_progress['n_report_iap_products'] >= MAX_PRODUCT_FAIL_REPORT:
            logger.warning('Too many product failures, stop reporting to IAP')
            return

        self._report_to_iap('report_ko', partial_error=True, error=traceback.format_exc())
        generation_progress['n_report_iap_products'] += 1
        self.generation_progress = generation_progress
        self.env.cr.commit()
