# Part of Odoo. See LICENSE file for full copyright and licensing details.
import unittest

from odoo.tests import TransactionCase, tagged
from odoo.addons.ai.utils.ai_utils import markdown_format, CustomMarkdown


@tagged("post_install", "-at_install")
@unittest.skipUnless(CustomMarkdown, "can't test markdown rendering without a markdown renderer")
class TestMarkdownFormatting(TransactionCase):

    def test_md_bold_boundaries_detection(self):
        """Test that markdown_format correctly detects bold boundaries"""
        text = "The **Lion**, the **Giraffe** and the **Zebra**"
        expected = "<p>The <strong>Lion</strong>, the <strong>Giraffe</strong> and the <strong>Zebra</strong></p>"
        self.assertEqual(markdown_format(text), expected)

    def test_md_italic_bold_standard_behavior(self):
        """Test that standard bold and italic markdown is converted properly to HTML."""
        self.assertEqual(markdown_format("This is *italic*, right?"), "<p>This is <em>italic</em>, right?</p>")
        self.assertEqual(markdown_format("Wait, *is this italic?*"), "<p>Wait, <em>is this italic?</em></p>")
        self.assertEqual(markdown_format("Make it **bold**, please!"), "<p>Make it <strong>bold</strong>, please!</p>")
        self.assertEqual(
            markdown_format("Look at this **bold with *italic* inside**, cool? And here is *italic with **bold** inside*, interesting."),
            "<p>Look at this <strong>bold with <em>italic</em> inside</strong>, cool? And here is <em>italic with <strong>bold</strong> inside</em>, interesting.</p>"
        )
        self.assertEqual(
            markdown_format("Finally, ***bold and italic*** together!"),
            "<p>Finally, <strong><em>bold and italic</em></strong> together!</p>"
        )
