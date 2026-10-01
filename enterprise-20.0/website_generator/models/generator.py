# Part of Odoo. See LICENSE file for full copyright and licensing details.
import html
import json
import logging
import re
import tarfile
import time
import traceback
from itertools import batched, islice
from urllib.parse import urlparse

import requests
from lxml import etree
from lxml import html as lxml_html
from psycopg2.errors import SerializationFailure

from odoo import _, api, fields, models
from odoo.exceptions import LockError
from odoo.tools.urls import urljoin

from odoo.addons.iap.tools.iap_tools import iap_jsonrpc
from odoo.addons.website_generator.utils.constants import (
    DEFAULT_WSS_ENDPOINT,
    STATUS_MESSAGES,
)

logger = logging.getLogger(__name__)

UNCROPPED_IMAGES_BATCH_SIZE = 10
CROPPED_IMAGES_PAGES_BATCH_SIZE = 10
PAGES_BATCH_SIZES = 5


class Website_GeneratorRequest(models.Model):
    _name = 'website_generator.request'
    _description = "Website Generator Request"

    target_url = fields.Char(string="URL to scrape", required=True)
    additional_urls = fields.Char(string="Additional URLs")
    page_count = fields.Integer(string="Number of pages")
    uuid = fields.Char(string="Output UUID generated from Website Scraper Server")
    status = fields.Char(string="Status", default='draft')
    status_message = fields.Char(string="Status Message", compute='_compute_status_message')
    version = fields.Char(string="Version", default='3.0.0')
    website_id = fields.Many2one('website', string="Website", ondelete='cascade')
    import_website = fields.Boolean(string='Import website', default=False)

    generation_progress = fields.Json()
    out_json_attachment_id = fields.Many2one('ir.attachment')

    @api.model_create_multi
    def create(self, vals_list):
        # Activate the cron first so that in case of lock and retry we don't send the same request twice
        cron_get_result = self.env.ref("website_generator.cron_get_result")
        self._activate_cron(cron_get_result)
        wg_requests = super().create(vals_list)
        for req in wg_requests:
            # If there is already a uuid, it means the request was already
            # created via the odoo.com start trial.
            if not req.uuid:
                ws_endpoint = self.env['ir.config_parameter'].sudo().get_str('website_scraper_endpoint') or DEFAULT_WSS_ENDPOINT
                url = urljoin(ws_endpoint, f'/website_scraper/{req.version}/scrape')
                response = iap_jsonrpc(url, params=req._get_call_params(), raise_user_error=True)
                if response.get('status') == 'accepted':
                    req.write({
                        'uuid': response['uuid'],
                        'status': 'waiting',
                    })
                    if response.get('cached'):
                        cron_get_result._trigger()
                else:
                    req.status = response.get('status', 'error_internal')
                    logger.warning("Error calling WS server: %s", req.status)
        return wg_requests

    @api.depends('status')
    def _compute_status_message(self):
        for record in self:
            record.status_message = self.env._(STATUS_MESSAGES.get(record.status, STATUS_MESSAGES['error_internal']))  # pylint: disable=gettext-variable

    def _get_call_params(self):
        ICP = self.env['ir.config_parameter'].sudo()
        params = {
            'url': self.target_url,
            'additional_urls': self.additional_urls,
            'token': ICP.get_str('website_generator.token') or None,
            'dbuuid': ICP.get_str('database.uuid'),
            'db_url': self.get_base_url(),
            'wg_request_id': self.id,
            'import_website': self.import_website,
        }
        if self.page_count:
            params['page_count'] = self.page_count
        return params

    @api.model
    def get_result_waiting_requests(self):
        """ This method is called by the CRON job which is toggled by the creation of a request. """
        ready_requests = self.search([
            ('status', 'in', ['waiting', 'error_request_still_processing', 'error_maintenance']),
        ])
        self.env['ir.cron']._commit_progress(remaining=len(ready_requests), deactivate=not ready_requests)
        for request in ready_requests:
            request._call_server_get_result()
            if request.status == 'ready_generate_site':
                cron_generate_site = self.env.ref('website_generator.cron_generate_site')
                self._activate_cron(cron_generate_site)
                cron_generate_site._trigger()
            self.env['ir.cron']._commit_progress(1)

    def cronless_call_server_and_generate_site(self):
        """
        WARNING: This method is strictly for the trial flow where the number of
        pages and products is low enough that we don't risk timeout.
        """
        self.ensure_one()
        self._call_server_get_result()
        if self.status == 'ready_generate_site':
            self._generate_site(0, 1)

    @staticmethod
    def _activate_cron(cron):
        # Attempt to do the following, but timeout=5 doesn't exist (yet)
        # cron.try_lock_for_update(timeout=5).toggle(model=self._name, domain=[])
        for i in range(50):  # watchdog
            if cron.try_lock_for_update():
                break
            time.sleep(.1)

        # We don't use the toggle function directly
        #  because it doesn't work on models with no records yet
        try:
            cron.lock_for_update(allow_referencing=True)
        except LockError:
            return True
        return cron.write({'active': True})

    def _call_server_get_result(self):
        try:
            logger.info("Website Generator: Getting result for request uuid: %s", self.uuid)
            ICP = self.env['ir.config_parameter'].sudo()
            data = {
                'dbuuid': ICP.get_str('database.uuid', None),
                'token': ICP.get_str('website_generator.token', None),
                'uuid': self.uuid,
                'db_url': self.get_base_url(),  # Necessary for the trial flow because we don't know the url when launching the request
            }
            ws_endpoint = ICP.get_str('website_scraper_endpoint', DEFAULT_WSS_ENDPOINT)

            # /get_result is not protected by token
            url = urljoin(ws_endpoint, f'/website_scraper/{self.version}/get_result')
            generation_progress = self._generation_progress_init()
            with requests.get(url, params=data, stream=True, timeout=(10, 30)) as r:
                r.raise_for_status()

                if r.headers.get('Content-Type', '') == 'text/html; charset=utf-8':
                    try:
                        self.status = r.json().get('status', 'error_internal')
                    except json.decoder.JSONDecodeError:
                        self.status = 'error_internal'
                    logger.warning('Website Generator: failed to fetch the result for request id %s, status: %s', self.id, self.status)
                    return
                if r.headers.get('Content-Type', '') != 'application/x-tar':
                    logger.error('Website Generator: Wrong content type of result for request id %s', self.id)
                    return

                # Open tar.gz in streaming mode
                with tarfile.open(fileobj=r.raw, mode="r|gz") as tar:
                    generation_progress['attachment_map'] = self._process_tar(tar)
                self.generation_progress = generation_progress
                self.status = 'ready_generate_site'
                logger.info("Website Generator: Finished fetch step for request uuid: %s", self.uuid)

        except SerializationFailure:
            # Here to re-trigger the cron in case of SerializationFailure
            raise
        except Exception:
            self.env.cr.rollback()
            self.status = 'error_internal'
            logger.exception("Error fetching the website: %s", self.target_url)

            # Report KO to IAP (useful for spotting critical errors)
            self._report_to_iap('report_ko', error=traceback.format_exc())
            self._send_notification()

    def _process_tar(self, tar):
        # Don't inline this method in `_call_server_get_result()`, it's needed for ease
        # of development (overridden in custom dev module)
        attachment_map = {}
        for i, member in enumerate(tar):
            if not member.isreg():
                continue

            if member.name.startswith("images/"):
                f = tar.extractfile(member)
                if not f:
                    continue
                image_name = member.name.removeprefix("images/")
                public = True
                # Customized images don't need to be shown
                if image_name.startswith('customized'):
                    public = False
                att = self.env['ir.attachment'].sudo().create({
                    'name': image_name,
                    'raw': f.read(),
                    'res_id': 0,
                    'res_model': 'ir.ui.view',
                    'public': public,
                })
                attachment_map[image_name] = {
                    'id': att.id,
                    'used': False,
                }
                if i % 10 == 0:
                    logger.info("Extracted images saved (total: %s)", i)

            elif member.name == "out.json":
                f = tar.extractfile(member)
                if not f:
                    continue

                self.out_json_attachment_id = self.env['ir.attachment'].sudo().create({
                    'name': member.name,
                    'raw': f.read(),
                })
                logger.info("Extracted out.json saved")
        return attachment_map

    def _generation_progress_init(self):
        return {
            'attachment_map': {},
            'direct_html_replacements_mapping': {},
            'image_url_to_filename': {},
            'last_uncropped_image_id': 0,
            'last_page_id': 0,
            'website_record_created': False,
            'homepage_done': False,
        }

    def _report_to_iap(self, endpoint, partial_error=False, error=None):
        try:
            ICP = self.env['ir.config_parameter'].sudo()
            data = {
                'dbuuid': ICP.get_str('database.uuid', None),
                'token': ICP.get_str('website_generator.token', None),
                'uuid': self.uuid,
            }
            if partial_error:
                data['partial_error'] = partial_error

            if error:
                data['error'] = error

            ws_endpoint = ICP.get_str('website_scraper_endpoint', DEFAULT_WSS_ENDPOINT)
            url = urljoin(ws_endpoint, f'/website_scraper/{self.version}/{endpoint}')
            resp = iap_jsonrpc(url, params=data)
            if resp.get('status') != 'ok':
                logger.warning("Error reporting to WS server: %s", resp.get('status'))
        except requests.RequestException as e:
            logger.warning("Error reporting to WS server: %s", e)

    def _get_ready_generate_site(self):
        ready_requests = self.search([
            ('status', '=', 'ready_generate_site'),
        ])
        total_requests = len(ready_requests)
        self.env['ir.cron']._commit_progress(remaining=total_requests, deactivate=total_requests == 0)
        for request_index, request in enumerate(ready_requests):
            request._generate_site(request_index, total_requests)
            self.env['ir.cron']._commit_progress(1)

    def _generate_site(self, request_index, total_requests):
        try:
            odoo_blocks = json.loads(self.out_json_attachment_id.raw.content)
            generation_progress = self.generation_progress
            generate_website = odoo_blocks.get('homepage') and self.import_website
            website_url = None
            if generate_website:
                # Create the website before products to link the website to the products
                self._set_website(odoo_blocks, generation_progress)
                self = self.with_context(website_id=self.website_id.id)  # noqa: PLW0642

            nbr_products_created = self._create_products(request_index, total_requests, odoo_blocks, generation_progress)

            nbr_blogs_posts_created = self._create_blogs(request_index, total_requests, odoo_blocks, generation_progress)

            # Generate the website only if there is a homepage
            if generate_website:
                self._generate_pages(odoo_blocks, generation_progress)
                domain = self.website_id.domain or self.website_id.get_base_url()
                if self.website_id.id == self.env["ir.http"]._get_host_id_from_domain(domain):
                    website_url = self.website_id.domain
                else:
                    self.website_id._force()
                    website_url = domain

            self.generation_progress = generation_progress
            self.status = 'done'
            # Report OK to IAP (success)
            self._report_to_iap('report_ok')
            self._send_notification(website_url=website_url, nbr_products_created=nbr_products_created, nbr_blogs_created=nbr_blogs_posts_created)
        except SerializationFailure:
            # Here to re-trigger CRON or retry RPC in case of SerializationFailure
            raise
        except Exception:
            self.env.cr.rollback()
            self.status = 'error_internal'
            logger.exception("Error importing website")
            self._report_to_iap('report_ko', error=traceback.format_exc())
            self._send_notification()

    def _send_notification(self, website_url=None, nbr_products_created=0, nbr_blogs_created=0):
        subject = _("Something went wrong during the import")
        if website_url and nbr_products_created > 0 and nbr_blogs_created > 0:
            subject = _("Your new website, blogs and products are ready!")
        elif website_url and nbr_products_created > 0:
            subject = _("Your new website and products are ready!")
        elif website_url and nbr_blogs_created > 0:
            subject = _("Your new website and blogs are ready!")
        elif nbr_products_created > 0 and nbr_blogs_created > 0:
            subject = _("Your new blogs and products are ready!")
        elif website_url:
            subject = _("Your new website is ready!")
        elif nbr_products_created > 0:
            subject = _("Your products have been imported!")
        elif nbr_blogs_created > 0:
            subject = _("Your blogs have been imported!")

        email_values = {
            'nbr_products_created': nbr_products_created,
            'nbr_blogs_created': nbr_blogs_created,
            'website_url': website_url,
        }
        body_html = (
            self.env.ref("website_generator.email_template_website_scrapped")
            .with_context(**email_values, lang=self.create_uid.partner_id.lang)
            ._render_field("body_html", [self.id])[self.id]
        )
        self.env['mail.thread'].with_context(lang=self.create_uid.partner_id.lang).message_notify(
            subject=subject,
            body=body_html,
            author_id=self.env.ref('base.partner_root').id,
            subtype_xmlid='mail.mt_comment',
            email_layout_xmlid='mail.mail_notification_light',
            partner_ids=[self.create_uid.partner_id.id],
            force_send=True,
        )

    def _create_products(self, request_index, total_requests, odoo_blocks, generation_progress):
        # Overriden in website_generator_sale, used for product generation
        return 0

    def _generate_pages(self, odoo_blocks, generation_progress):
        # Set attachments for all images (direct)
        all_images = odoo_blocks['website'].get('all_images', {})
        last_uncropped_image_id = generation_progress['last_uncropped_image_id']
        for uncropped_images_batch in batched(islice(all_images.items(), last_uncropped_image_id, None), UNCROPPED_IMAGES_BATCH_SIZE):
            uncropped_images_filenames = [img_name for img_url, img_name in uncropped_images_batch if img_url not in generation_progress['image_url_to_filename']]
            attachments_map = self._get_wg_attachment(uncropped_images_filenames, generation_progress, reuse=True)
            for img_url, img_name in uncropped_images_batch:
                attachment = attachments_map.get(img_name)
                if img_url in generation_progress['image_url_to_filename'] or not attachment:
                    continue

                generation_progress['image_url_to_filename'][img_url] = img_name
                generation_progress['direct_html_replacements_mapping'][html.escape(img_url)] = attachment.image_src

            generation_progress['last_uncropped_image_id'] = min(len(all_images), generation_progress['last_uncropped_image_id'] + UNCROPPED_IMAGES_BATCH_SIZE)
            logger.info("Importing images: %s/%s", generation_progress['last_uncropped_image_id'], len(all_images))
            self.generation_progress = generation_progress
            # Commit progress only looks if process was done and if there is some remaining
            # Since the remaining is hard to know depending on the context and a bit meaningless, we avoid doing complex computation
            # We just set these values to say that there was progress and that their is still work to do
            self.env['ir.cron']._commit_progress(processed=1, remaining=1)

        # Load direct replacements
        direct_html_replacements_mapping = generation_progress['direct_html_replacements_mapping']
        sorted_original_html = sorted(direct_html_replacements_mapping.keys(), key=len, reverse=True)
        pattern_sorted_html = r'(' + '|'.join(map(re.escape, sorted_original_html)) + r')'

        if not generation_progress['homepage_done']:
            # Remove the default homepage
            homepage_url = self.website_id.homepage_url or '/'
            self.env['website.page'].sudo().search([('website_id', '=', self.website_id.id), ('url', '=', homepage_url)]).unlink()

            # Create new homepage
            homepage_info = self.website_id.with_context(website_id=self.website_id.id).new_page('Home')
            homepage = self.env['website.page'].sudo().browse(homepage_info['page_id'])
            homepage.sudo().write({
                'url': '/',
                'is_published': True,
            })

            # Replacements
            hompage_data = odoo_blocks['homepage']
            image_replacement_mapping = self._save_customized_images_as_attachments(hompage_data, generation_progress)
            hompage_data['body_html'] = self._apply_html_replacements(hompage_data.get('body_html', []), pattern_sorted_html, direct_html_replacements_mapping, image_replacement_mapping)
            footer = hompage_data.get('footer', [])
            if footer:
                hompage_data['footer'] = self._apply_html_replacements(footer, pattern_sorted_html, direct_html_replacements_mapping, image_replacement_mapping)
            header_buttons = hompage_data.get('header', {}).get('buttons', [])
            for button in header_buttons:
                if button.get('href') in direct_html_replacements_mapping:
                    button['href'] = direct_html_replacements_mapping[button['href']]

            # Create homepage content
            homepage._construct_homepage(hompage_data)

            # Save progress
            generation_progress['homepage_done'] = True
            self.generation_progress = generation_progress
            # Commit progress only looks if process was done and if there is some remaining
            # Since the remaining is hard to know depending on the context and a bit meaningless, we avoid doing complex computation
            # We just set these values to say that there was progress and that their is still work to do
            self.env['ir.cron']._commit_progress(processed=1, remaining=1)

        # Create pages
        pages = odoo_blocks.get('pages', {}).items()
        last_page_id = generation_progress['last_page_id']
        for pages_batch in batched(islice(pages, last_page_id, None), PAGES_BATCH_SIZES):
            for page_url, page_data in pages_batch:
                if 'body_html' not in page_data:
                    continue

                # Create page
                new_page_info = self.website_id.with_context(website_id=self.website_id.id).new_page(page_data['name'])
                new_page = self.env['website.page'].sudo().browse(new_page_info['page_id'])
                # force url to the one provided, don't use the slugified one
                new_page.url = page_url
                new_page.is_published = True

                # Replacements
                image_replacement_mapping = self._save_customized_images_as_attachments(page_data, generation_progress)
                page_data['body_html'] = self._apply_html_replacements(page_data.get('body_html', []), pattern_sorted_html, direct_html_replacements_mapping, image_replacement_mapping)

                # Create page content
                new_page._construct_page(page_data)
            generation_progress['last_page_id'] = min(len(pages), generation_progress['last_page_id'] + PAGES_BATCH_SIZES)
            logger.info("Importing pages: %s/%s", generation_progress['last_page_id'], len(pages))
            self.generation_progress = generation_progress
            # Commit progress only looks if process was done and if there is some remaining
            # Since the remaining is hard to know depending on the context and a bit meaningless, we avoid doing complex computation
            # We just set these values to say that there was progress and that their is still work to do
            self.env['ir.cron']._commit_progress(processed=1, remaining=1)

    def _set_website(self, odoo_blocks, generation_progress):
        if generation_progress.get('website_record_created'):
            return

        website_info = odoo_blocks.get('website')
        if not website_info:
            msg = "Website info not found in the input"
            raise ValueError(msg)
        homepage_url = odoo_blocks.get('homepage', {}).get('url')
        if not homepage_url:
            msg = "Homepage url not found in the input"
            raise ValueError(msg)
        website_name = urlparse(homepage_url).netloc.removeprefix('www.')

        # Avoid duplicate website names
        all_websites = self.env['website'].sudo().search([])
        for website in all_websites:
            if website_name in website.name:
                website_name = f'{website_name} ({len(all_websites)})'
                break

        website_values = {'name': website_name}
        if not self.website_id:
            # Create a new website
            website = self.env['website'].sudo().create(website_values)
            self.write({'website_id': website.id})
        else:
            self.website_id.update(website_values)

        social_media_links = {platform: link for platform, link in website_info.get('social_media_links', {}).items() if link}
        if social_media_links:
            self.website_id.company_id.sudo().write(social_media_links)

        # Add logo
        logo_filename = website_info.get('logo')
        att = self._get_wg_attachment([logo_filename], generation_progress, reuse=False).get(logo_filename)
        if att:
            att.update({
                'res_field': 'logo',
                'res_id': self.website_id.id,
                'res_model': 'website',
            })

        generation_progress['website_record_created'] = True
        self.generation_progress = generation_progress
        # Commit progress only looks if process was done and if there is some remaining
        # Since the remaining is hard to know depending on the context and a bit meaningless, we avoid doing complex computation
        # We just set these values to say that there was progress and that their is still work to do
        self.env['ir.cron']._commit_progress(processed=1, remaining=1)

    def _create_blogs(self, request_index, total_requests, odoo_blocks, generation_progress):
        # Overriden in website_generator_blog, used for blog generation
        return 0

    def _get_wg_attachment(self, filenames, generation_progress, reuse=True):
        if not filenames:
            return {}

        unique_filenames = list(dict.fromkeys(filenames))

        fname_to_id = {
            name: generation_progress['attachment_map'][name]['id']
            for name in unique_filenames
            if generation_progress['attachment_map'].get(name)
        }

        if not fname_to_id:
            return {}

        all_attachments = self.env['ir.attachment'].sudo().browse(fname_to_id.values()).exists()
        att_lookup = {att.id: att for att in all_attachments}

        results = {}
        # Make sure we loop over unique_filenames instead of filenames because otherwise we make
        # redudant copies that are never used.
        for filename in unique_filenames:
            att_id = fname_to_id.get(filename)
            att = att_lookup.get(att_id)
            if not att:
                logger.error('Website Generator: Attachment id not found: %s for filename: %s', att_id, filename)
                continue

            attachment_info = generation_progress['attachment_map'][filename]

            # If we cannot reuse (reuse=False and already used), add to copy list
            if not reuse and attachment_info.get('used'):
                # Batch copying not supported if the recordset has duplicates
                results[filename] = att.copy()
            else:
                results[filename] = att
                attachment_info['used'] = True

        return results

    def _save_customized_images_as_attachments(self, page_data, generation_progress):
        # Process every image on the page (not just the uncropped ones)
        customized_images = page_data.get('images_to_customize', {})
        image_replacement_mapping = {}
        original_image_filenames = []
        custom_image_filenames = []
        for ws_id, image_customizations in customized_images.items():
            custom_image_filename = image_customizations.get('filename')
            mimetype = image_customizations.get('mimetype')
            original_image_url = image_customizations.get('url')
            if not custom_image_filename or not mimetype or not original_image_url or not ws_id:
                continue

            original_image_att_filename = generation_progress['image_url_to_filename'].get(original_image_url)
            image_customizations['original_image_att_filename'] = original_image_att_filename
            if not original_image_att_filename:
                continue

            original_image_filenames.append(original_image_att_filename)
            if image_customizations.get('create_new_attachment', False):
                custom_image_filenames.append(custom_image_filename)

        filename_attachment_map = self._get_wg_attachment(original_image_filenames, generation_progress, reuse=True)
        custom_image_filename_attachment_map = self._get_wg_attachment(custom_image_filenames, generation_progress, reuse=True)
        for ws_id, image_customizations in customized_images.items():
            original_image_att_filename = image_customizations.get('original_image_att_filename')
            attachment = filename_attachment_map.get(original_image_att_filename)
            if not attachment:
                continue

            custom_image_filename = image_customizations.get('filename')
            mimetype = image_customizations.get('mimetype')

            # Set the original image src
            src = attachment.image_src

            # Create a new attachment if needed
            custom_image_attachment = custom_image_filename_attachment_map.get(custom_image_filename)
            if custom_image_attachment:
                src = custom_image_attachment.image_src

            attributes = {
                'src': src,
                'data-attachment-id': attachment.id,
                'data-original-id': attachment.id,
                'data-original-src': attachment.image_src,
                'data-mimetype': mimetype,
                'data-mimetype-before-conversion': mimetype,
            }

            # Apply the cropping attributes
            cropping_dimensions = image_customizations.get('cropping_coords', {})
            if cropping_dimensions:
                attributes.update({
                    'data-x': cropping_dimensions['x'],
                    'data-y': cropping_dimensions['y'],
                    'data-width': cropping_dimensions['width'],
                    'data-height': cropping_dimensions['height'],
                    'data-scale-x': 1,
                    'data-scale-y': 1,
                    'data-aspect-ratio': '0/0',
                })

            color_filter = image_customizations.get('filter', {})
            if color_filter:
                rgba = f'rgba({int(color_filter["coords"][0] * 255)}, {int(color_filter["coords"][1] * 255)}, {int(color_filter["coords"][2] * 255)}, {color_filter["alpha"]})'
                attributes.update({
                    'data-gl-filter': 'custom',
                    'data-filter-options': json.dumps({'filterColor': rgba}, separators=(',', ':')),
                })

            image_replacement_mapping[str(ws_id)] = attributes
        return image_replacement_mapping

    def _apply_html_replacements(self, body_html, pattern_sorted_html, direct_replacement_mapping,
                                 image_replacement_mapping, template_key_to_filter_xmlid=None):
        template_key_to_filter_xmlid = template_key_to_filter_xmlid or {}
        template_key_to_filter_id = {
            tk: self.env.ref(xmlid).id
            for tk, xmlid in template_key_to_filter_xmlid.items()
            if self.env.ref(xmlid, raise_if_not_found=False)
        }

        new_block_list = []
        for block_html in body_html:
            page_html = self._replace_in_string(block_html, pattern_sorted_html, direct_replacement_mapping)
            page_html = self._update_html(page_html, image_replacement_mapping, template_key_to_filter_id)
            new_block_list.append(page_html)
        return new_block_list

    @staticmethod
    def _update_html(page_html, image_replacement_mapping, template_key_to_filter_id):
        if not image_replacement_mapping and not template_key_to_filter_id:
            return page_html

        try:
            container = lxml_html.fragment_fromstring(page_html.replace('\ufeff', ''), create_parent='div')
        except (etree.ParserError, ValueError) as e:
            logger.warning("Could not parse snippet for image replacement: %s", e)
            return page_html

        for el in container.xpath('.//*[@data-template-key]'):
            target_filter_id = template_key_to_filter_id.get(el.get('data-template-key'))
            if target_filter_id:
                el.set('data-filter-id', str(target_filter_id))

        for img in container.xpath('.//img[@data-ws_id]'):
            replacement_attrs = image_replacement_mapping.get(img.get('data-ws_id'))
            if not replacement_attrs:
                continue

            new_img = lxml_html.Element('img')
            for attribute, value in replacement_attrs.items():
                new_img.set(attribute, str(value))

            # Preserve the original class/style attributes
            img_class = img.get('class')
            if img_class:
                new_img.set('class', img_class)
            img_style = img.get('style')
            if img_style:
                new_img.set('style', img_style)

            # data-ws-preserve contains raw attributes to carry over to the new image.
            preserved_attributes = (img.get('data-ws-preserve') or '').strip()
            if preserved_attributes:
                try:
                    attributes = json.loads(preserved_attributes)
                    for attribute, value in attributes.items():
                        new_img.set(attribute, value)
                except (TypeError, ValueError, UnicodeDecodeError) as e:
                    logger.warning("Could not parse preserved img attributes %r: %s", preserved_attributes, e)

            img.getparent().replace(img, new_img)

        # Serialize only the fragment content, not the temporary wrapper element
        # created by fragment_fromstring(..., create_parent='div').
        return (container.text or '') + ''.join(
            etree.tostring(child, encoding='unicode')
            for child in container
        )

    @staticmethod
    def _replace_in_string(string, pattern_sorted_html, replacements):
        if not replacements:
            return string

        def replace_callback(match):
            # Having this callback function is useful for verifying which URLs were replaced.
            matched_url = match.group(0)
            replacement = replacements.get(matched_url)
            if not replacement:
                replacement = matched_url
                logger.warning("Match found but URL %r not found in attachments", matched_url)
            return replacement

        # Replace all matches with their corresponding replacement
        return re.sub(pattern_sorted_html, replace_callback, string)

    @api.model
    def convert_scraping_request_ICP(self):
        ICP = ws_uuid = self.env['ir.config_parameter'].sudo()
        ws_uuid = ICP.get_str('website_generator.iap_ws_uuid')
        ws_target_url = ICP.get_str('website_generator.iap_ws_target_url')

        if not (ws_uuid and ws_target_url):
            # Fallback to the website configurator
            return self.env.ref('website.action_open_website_configurator').read()[0]

        self.env['website_generator.request'].sudo().create({
            'uuid': ws_uuid,
            'target_url': ws_target_url,
            'import_website': True,
            'status': 'waiting',
            'website_id': self.env.website.id,  # Makes sure the website is put on the first website instead of creating a new one.
        })
        ICP.set_str('website_generator.iap_ws_uuid', None)
        ICP.set_str('website_generator.iap_ws_target_url', None)

        return {
            'type': 'ir.actions.act_url',
            'url': "/odoo/action-website_generator.website_generator_screen?reload=true",
            'target': 'self',
        }

    @api.model
    def has_api_setup(self, platform):
        ICP = self.env['ir.config_parameter'].sudo()
        db_uuid = ICP.get_str('database.uuid')

        ws_path = ICP.get_str('website_scraper_endpoint') or DEFAULT_WSS_ENDPOINT
        ws_url = urljoin(ws_path, '/website_scraper/has_active_api_key')
        return iap_jsonrpc(ws_url, params={'db_uuid': db_uuid, 'platform': platform})

    @api.model
    def apply_api_key(self, platform='', consumer_key='', consumer_secret='', validate=False, target_url=''):
        ICP = self.env['ir.config_parameter'].sudo()
        db_uuid = ICP.get_str('database.uuid')

        ws_endpoint = ICP.get_str('website_scraper_endpoint') or DEFAULT_WSS_ENDPOINT
        url = urljoin(ws_endpoint, '/website_scraper/create_api_key_record')
        params = {
            'db_uuid': db_uuid,
            'platform': platform,
            'consumer_key': consumer_key,
            'consumer_secret': consumer_secret,
            'validate': validate,
            'url': target_url,
        }
        return iap_jsonrpc(url, params=params, raise_user_error=True)

    @api.model
    def get_system_parameters(self):
        ICP = self.env['ir.config_parameter'].sudo()
        db_uuid = ICP.get_str('database.uuid')
        db_url = ICP.get_str('web.base.url')
        ws_endpoint = ICP.get_str('website_scraper_endpoint') or DEFAULT_WSS_ENDPOINT
        return [db_uuid, db_url, ws_endpoint]
