# Part of Odoo. See LICENSE file for full copyright and licensing details.
import random
from typing import NamedTuple

from lxml import html as lxml_html

from odoo import api, models


class SnippetHint(NamedTuple):
    group: str
    label: str
    intent: str


_SNIPPET_GROUPS = {
    'hero': "Hero / Opening",
    'content': "Content layout",
    'cta': "Call to action",
    'social_proof': "Social proof",
    'media': "Media / Imagery",
    'data': "Data / Statistics",
    'form': "Form / Contact",
    'other': "Catalog / Pricing",
}

_SNIPPET_HINTS = {
    # group, label, intent hint
    's_banner': SnippetHint('hero', "Banner", "prominent hero with a large headline and a call-to-action button"),
    's_cover': SnippetHint('hero', "Cover", "full-screen background image with centered text and a primary CTA"),
    's_picture': SnippetHint('hero', "Title - Image", "centered title and subtitle above a large full-width image"),
    's_motto': SnippetHint('hero', "Motto", "large prominent quote or motto"),
    's_title': SnippetHint('hero', "Title", "centered prominent heading to separate parts of a page"),
    's_text_block': SnippetHint('content', "Text", "single-column text area for paragraphs / long-form content"),
    's_text_image': SnippetHint('content', "Text - Image", "side-by-side: text left, image right"),
    's_image_text': SnippetHint('content', "Image - Text", "side-by-side: image left, text right"),
    's_image_text_overlap': SnippetHint('content', "Image - Text Overlap", "overlapping grid of a large image and a text box"),
    's_image_frame': SnippetHint('content', "Image Frame", "single large image in a styled frame"),
    's_three_columns': SnippetHint('content', "Columns", "three-column grid of cards with top images and text"),
    's_features': SnippetHint('content', "Features", "multi-column feature grid with icons and short text"),
    's_key_images': SnippetHint('content', "Key Images", "numbered steps paired with images and short text"),
    's_color_blocks_2': SnippetHint('content', "Color Blocks", "side-by-side colored boxes with text and CTA buttons"),
    's_striped': SnippetHint('content', "Striped section", "alternating striped-background rows of text"),
    's_card_offset': SnippetHint('content', "Card Offset", "overlapping large image with an offset text card"),
    's_cards_grid': SnippetHint('content', "Cards Grid", "multi-column grid of horizontal cards with images and text"),
    's_masonry_block': SnippetHint('content', "Masonry", "asymmetric masonry grid combining images and text"),
    's_media_list': SnippetHint('content', "Media List", "vertical list of items with side-by-side image and text"),
    's_tabs': SnippetHint('content', "Tabs", "horizontal tabbed navigation between content areas"),
    's_faq_collapse': SnippetHint('content', "FAQ", "collapsible accordion of questions and answers"),
    's_faq_horizontal': SnippetHint('content', "Topics List", "horizontal list of topics or steps with text"),
    's_faq_list': SnippetHint('content', "FAQ List", "multi-column grid of questions and answers (no collapse)"),
    's_call_to_action': SnippetHint('cta', "Call to Action", "horizontal banner with a strong headline and a CTA button"),
    's_cta_card': SnippetHint('cta', "Card Call to Action", "prominent text paired with a card holding a CTA button"),
    's_company_team': SnippetHint('social_proof', "Team", "team members with circular photos and names"),
    's_quotes_carousel': SnippetHint('social_proof', "Quotes", "sliding carousel of testimonials or quotes"),
    's_reviews_wall': SnippetHint('social_proof', "Reviews Wall", "multi-column grid of customer review cards"),
    's_references': SnippetHint('social_proof', "References", "horizontal row of partner / client logos"),
    's_carousel': SnippetHint('media', "Carousel", "sliding image carousel with text and CTA per slide"),
    's_carousel_cards': SnippetHint('media', "Carousel Cards", "sliding carousel of multiple cards per slide"),
    's_images_wall': SnippetHint('media', "Images Wall", "masonry grid of images of varying sizes"),
    's_parallax': SnippetHint('media', "Parallax", "full-width parallax background image with overlay content"),
    's_big_number': SnippetHint('data', "Big number", "single massive number / statistic centered on screen"),
    's_numbers': SnippetHint('data', "Numbers", "row of large prominent numbers with short labels"),
    's_process_steps': SnippetHint('data', "Process Steps", "horizontal sequence of steps connected by lines"),
    's_timeline': SnippetHint('data', "Timeline", "vertical timeline of milestones or events with dates"),
    's_timeline_images': SnippetHint('data', "Timeline Images", "vertical timeline pairing milestones with images"),
    's_comparisons': SnippetHint('data', "Comparisons", "side-by-side pricing plan cards comparing features and cost"),
    's_opening_hours': SnippetHint('data', "Opening Hours", "business opening hours over a parallax background"),
    's_title_form': SnippetHint('form', "Title - Form", "centered title and text above a simple form"),
    's_form_aside': SnippetHint('form', "Form Aside", "side-by-side contact info and an input form"),
    's_website_form_cover': SnippetHint('form', "Form Cover", "split layout with a large background image and a form"),
    's_contact_info': SnippetHint('form', "Contact Info", "grid of contact details (address, phone, etc.)"),
    's_attributes_horizontal': SnippetHint('other', "Horizontal Attributes", "row of small icons/images with short labels"),
    's_pricelist_boxed': SnippetHint('other', "Pricelist Boxed", "centered boxed pricing menu over a parallax background"),
    's_pricelist_cafe': SnippetHint('other', "Pricelist Cafe", "multi-column cafe/restaurant menu with items and prices"),
    's_product_catalog': SnippetHint('other', "Pricelist", "detailed product/menu list with a background image"),
    's_product_list': SnippetHint('other', "Product List", "multi-column grid of product cards with images and links"),
    's_ecomm_categories_showcase': SnippetHint('other', "Categories Grid", "grid of e-commerce categories with background images"),
}


class AIWebsiteService(models.AbstractModel):
    _inherit = 'ai.website.service'

    @api.ormcache()
    def _render_snippets(self):
        website_id = self.env.website.id or self.env.context.get('host_id') or self.env.ref('base.default_website').id
        snippets_html = self.env["ir.ui.view"].with_context({
            "website_id": website_id,
            "inherit_branding": False,
        }).render_public_asset("website.snippets", values={})
        return lxml_html.fromstring(f'<div>{snippets_html}</div>')

    @api.model
    def _create_snippets_list(self):
        """The curated snippet menu (see _SNIPPET_HINTS), grouped by purpose.
        Order within a group is randomised each run so picks rotate (a fixed
        order made every hero an s_banner)."""
        snippets_tree = self._render_snippets()
        tags_by_key = {}
        snippets = snippets_tree.xpath('.//snippets[@id="snippet_structure" or @id="snippet_content"]/*')
        for snippet in snippets:
            key = snippet.get('data-oe-snippet-key')
            if key in _SNIPPET_HINTS:
                tags_by_key[key] = snippet.get('data-oe-keywords') or ""

        keys_by_group = {}
        for key in tags_by_key:
            keys_by_group.setdefault(_SNIPPET_HINTS[key].group, []).append(key)

        out = (
            "# Available snippets\n"
            "The building blocks you can use, grouped by purpose. Each has a unique "
            "key (use it to reference the snippet), a label and an intent hint.\n\n"
        )
        for group, group_label in _SNIPPET_GROUPS.items():
            keys = keys_by_group.get(group)
            if not keys:
                continue
            random.shuffle(keys)
            out += f'## {group_label}\n| Key | Label | Hint | Tags |\n| --- | --- | --- | --- |\n'
            for key in keys:
                hint = _SNIPPET_HINTS[key]
                out += f'| {key} | {hint.label} | {hint.intent} | {tags_by_key[key]} |\n'
            out += "\n"
        return out

    @api.model
    def _get_snippet_html(self, snippet_key):
        """Return `(hint, html)` for one catalog snippet: `hint` is the
        `SnippetHint` from `_SNIPPET_HINTS`, or `None` if the key isn't curated;
        `html` is the snippet's structure, or `None` if no snippet matches the
        key at all."""
        snippets_tree = self._render_snippets()
        section = snippets_tree.xpath(
            './/snippets[@id="snippet_structure" or @id="snippet_content"]'
            '//div[@data-oe-snippet-key=$key]/*[1]',
            key=snippet_key,
        )
        html = lxml_html.tostring(section[0], encoding='unicode') if section else None
        return _SNIPPET_HINTS.get(snippet_key), html
