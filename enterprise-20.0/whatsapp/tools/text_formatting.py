import re
from markupsafe import Markup

from odoo.tools import plaintext2html


def format_wa_markup_to_html(body_html):
    """
        Convert WhatsApp format text to HTML format text
        *bold* -> <b>bold</b>
        _italic_ -> <i>italic</i>
        ~strikethrough~ -> <s>strikethrough</s>
        ```monospace``` -> <code>monospace</code>
    """
    if not body_html:
        return Markup()

    formatted_body = str(plaintext2html(body_html))  # stringify for regex
    formatted_body = re.sub(r'\*(.*?)\*', r'<b>\1</b>', formatted_body)
    formatted_body = re.sub(r'\b_([^_\s][^_]*?[^_\s])_\b', r'<i>\1</i>', formatted_body)  # apply italic when whitespace surrounded for not breaking urls
    formatted_body = re.sub(r'~(.*?)~', r'<s>\1</s>', formatted_body)
    formatted_body = re.sub(r'```(.*?)```', r'<code>\1</code>', formatted_body)
    return Markup(formatted_body)
