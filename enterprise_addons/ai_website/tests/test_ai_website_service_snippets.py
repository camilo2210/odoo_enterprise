# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo.tests import tagged

from odoo.addons.ai.tests.common import TestAICommon
from odoo.addons.ai_website.models.ai_website_service_snippets import (
    _SNIPPET_GROUPS,
    _SNIPPET_HINTS,
)


@tagged('post_install', '-at_install')
class TestAIWebsiteServiceSnippets(TestAICommon):

    def test_only_curated_snippets_are_offered(self):
        """The list is an allowlist: anything the AI is offered must have a hint."""
        result = self.env['ai.website.service']._create_snippets_list()
        self.assertIn('# Available snippets', result)

        offered = set(re.findall(r'^\| (s_\w+) \|', result, re.MULTILINE))
        self.assertTrue(offered, "the snippet list should not be empty")
        self.assertFalse(offered - set(_SNIPPET_HINTS),
                         "every offered snippet must be in the curated catalog")

        # Each row carries the key, its label and its intent hint.
        for key in offered:
            hint = _SNIPPET_HINTS[key]
            self.assertIn(f'| {key} | {hint.label} | {hint.intent} |', result)

        groups = set(re.findall(r'^## (.+)$', result, re.MULTILINE))
        self.assertFalse(groups - set(_SNIPPET_GROUPS.values()),
                         "snippets should only be grouped under the declared purposes")

    def test_render_snippets(self):
        snippets_tree = self.env['ai.website.service']._render_snippets()

        self.assertTrue(snippets_tree.xpath('.//snippets[@id="snippet_structure"]'))
        self.assertFalse(
            snippets_tree.xpath('.//*[@data-oe-model="ir.ui.view"]'),
            "Rendered snippets should not contain view-branding attributes.",
        )

    def test_get_snippet_html(self):
        """A curated key returns its hint and structure; an unknown key returns neither."""
        hint, html = self.env['ai.website.service']._get_snippet_html('s_banner')
        self.assertEqual(hint, _SNIPPET_HINTS['s_banner'])
        self.assertIn('data-snippet="s_banner"', html)

        hint, html = self.env['ai.website.service']._get_snippet_html('not_a_real_snippet')
        self.assertIsNone(hint)
        self.assertIsNone(html)
