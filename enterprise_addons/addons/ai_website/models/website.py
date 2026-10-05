# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree

from odoo import api, fields, models


class Website(models.CachedModel):
    _inherit = 'website'

    ai_allow_scripts = fields.Boolean(
        string="AI JavaScript",
        help="Always let the AI website builder add JavaScript to the pages of this website.\n"
             "When off, it asks before adding any scripts.",
        default=False)

    @api.model
    def get_site_profile(self):
        website = self.env.website or self.env.website.browse(self.env.context.get('host_id')) or self.env.ref('base.default_website')
        company = website.company_id

        def _menu_to_dict(menu):
            return {
                'name': menu.name,
                'url': menu.url,
                'children': [_menu_to_dict(child) for child in menu.child_id.sorted('sequence')],
            }

        pages = self.env['website.page'].search_fetch([
            ('website_id', 'in', [website.id, False]),
        ], ['name', 'url', 'is_published'])

        return {
            'website_name': website.name,
            'domain': website.domain,
            'homepage_url': website.homepage_url,
            'default_language': {
                'code': website.default_lang_id.code,
                'name': website.default_lang_id.name,
            },
            'languages': [
                {'code': lang.code, 'name': lang.name}
                for lang in website.language_ids
            ],
            'company': {
                'name': company.name,
                'tagline': company.report_header,
                'street': company.street,
                'city': company.city,
                'zip': company.zip,
                'state': company.state_id.name,
                'country': company.country_id.name,
                'email': company.email,
                'phone': company.phone,
                'website': company.website,
            },
            'menu_tree': [
                _menu_to_dict(m)
                for m in website.menu_id.child_id.sorted('sequence')
            ],
            'pages': [
                {'name': page.name, 'url': page.url, 'is_published': page.is_published}
                for page in pages
            ],
        }

    @api.model
    def get_page_html(self, url, website_id):
        """Return the innerHTML of div#wrap for a website page.

        :param url: page URL.
        :param website_id: the website id.
        :return: HTML string of the div#wrap content, or None if not found.
        """
        page = self.env['website.page'].search_fetch([
            ('url', '=', url),
            ('website_id', '=', website_id),
        ], ['view_id'], limit=1)
        if not page:
            # Website pages may be shared by all websites (website_id=False).
            page = self.env['website.page'].search_fetch([
                ('url', '=', url),
                ('website_id', '=', False),
            ], ['view_id'], limit=1)
        if not page:
            return None

        website = self.env['website'].browse(website_id)
        arch_tree = page.view_id.sudo().with_context(
            inherit_branding=False, website_id=website_id, lang=website.default_lang_id.code,
        )._get_combined_arch()

        wrap_els = arch_tree.xpath('.//div[@id="wrap"]')
        if not wrap_els:
            return None

        return etree.tostring(wrap_els[0], encoding='unicode', method='html')
