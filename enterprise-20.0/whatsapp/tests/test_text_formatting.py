from odoo.addons.whatsapp.tools.text_formatting import format_wa_markup_to_html
from odoo.tests.common import BaseCase


class TextFormatting(BaseCase):
    def test_format_wa_markup_to_html(self):
        """Test the conversion of WhatsApp formatted text to HTML."""
        test_cases = [
            ('*bold*', '<p><b>bold</b></p>'),
            ('~strikethrough~', '<p><s>strikethrough</s></p>'),
            ('```monospace```', '<p><code>monospace</code></p>'),
            ('Here is _some text_ in italics', '<p>Here is <i>some text</i> in italics</p>'),
            # URLs with underscores should not be affected
            ('Visit https://example.com?access_token=abc123_def456',
            '<p>Visit <a href="https://example.com?access_token=abc123_def456" target="_blank" rel="noreferrer noopener">https://example.com?access_token=abc123_def456</a></p>'),
            # Mixed content - italic with urls and underscores
            ('This is _italic_ and visit https://example.com?token=abc_123',
            '<p>This is <i>italic</i> and visit <a href="https://example.com?token=abc_123" target="_blank" rel="noreferrer noopener">https://example.com?token=abc_123</a></p>'),
            # Multiple italic formatting
            ('Both _first_ and _second_ are italic',
            '<p>Both <i>first</i> and <i>second</i> are italic</p>'),
            # Edge case
            ('_italic_text_with_underscores_', '<p>_italic_text_with_underscores_</p>'),  # Should not match
            # Combined formatting italic and bold
            ('*Bold* and _italic_ with url_param=value',
            '<p><b>Bold</b> and <i>italic</i> with url_param=value</p>'),
        ]

        for body_html, expected in test_cases:
            with self.subTest(body_html=body_html):
                result = format_wa_markup_to_html(body_html)
                self.assertEqual(result, expected)
