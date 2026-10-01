# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.urls import urljoin as url_join

from odoo.addons.iap.tools.iap_tools import iap_jsonrpc
from odoo.addons.website_generator.models.generator import DEFAULT_WSS_ENDPOINT


class Website(models.Model):
    _inherit = 'website'

    @api.model
    def import_website(self, **kwargs):
        vals = {
            **kwargs,
            'target_url': self._normalize_domain_url(kwargs['target_url'].strip()),
            'website_id': kwargs.get('website_id'),
        }

        modules_to_install = self.env['ir.module.module']

        # website_generator_sale
        if kwargs.get('import_products') or kwargs.get('ecommerce_platform'):
            module = self.env['ir.module.module'].search([('name', '=', 'website_generator_sale')])
            if module.state != 'installed':
                modules_to_install += module

        # Make sure we don't have extra vals which shouldn't be there if website_generator_blog is not installed
        if not vals.get('blog_platform') or not vals.get('blog_platform'):
            vals.pop('import_blogs', None)
            vals.pop('blog_platform', None)
        else:
            module = self.env['ir.module.module'].search([('name', '=', 'website_generator_blog')])
            if module.state != 'installed':
                modules_to_install += module

        # install modules
        if modules_to_install:
            modules_to_install.button_immediate_install()

        request = self.env['website_generator.request'].create(vals)

        if request.status != 'waiting':
            raise UserError(request.status_message)

        return True

    @api.model
    def url_check(self, url_to_check):
        if not url_to_check:
            return {'status': 'empty_url'}

        self.env['website_generator.request'].check_access('create')
        target_url = self._normalize_domain_url(url_to_check)

        ICP = self.env['ir.config_parameter'].sudo()
        ws_endpoint = ICP.get_str('website_scraper_endpoint', DEFAULT_WSS_ENDPOINT)
        url = url_join(ws_endpoint, '/website_scraper/check_url_reachable')
        params = {
            'url': target_url,
        }

        return iap_jsonrpc(url, params=params, raise_user_error=True)

    @api.model
    def url_check_api(self, url_to_check):
        if not url_to_check:
            return {'status': 'empty_url'}

        self.env['website_generator.request'].check_access('create')
        target_url = self._normalize_domain_url(url_to_check)

        ICP = self.env['ir.config_parameter'].sudo()
        ws_endpoint = ICP.get_str('website_scraper_endpoint', DEFAULT_WSS_ENDPOINT)
        url = url_join(ws_endpoint, '/website_scraper/check_url_api')
        params = {
            'url': target_url,
            'version': '1.1',
        }

        return iap_jsonrpc(url, params=params, raise_user_error=True)
