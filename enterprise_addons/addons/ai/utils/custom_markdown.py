import re
import logging
try:
    import markdown2
except ImportError:
    logging.getLogger(__name__).warning("The library 'markdown2' is missing, cannot render markdown elements.")
    markdown2 = None

if markdown2:
    class CustomMarkdown(markdown2.Markdown):
        # Fixes an error where markdown2 2.4.11 doesn't detect the boundaries of bold markup properly. For example, "The **Lion**,
        # the **Giraffe** and the **Zebra**" becomes "The <strong>Lion<em>*, the *</em>Giraffe<em>* and the *</em>Zebra</strong>"
        # where it should be "The <strong>Lion/Giraffe/Zebra</strong>".
        # The updated regex definition for detecting bold markup is copied from markdown2 2.5.4 which solves the issue.
        # This should be removed when the Odoo version 20 is released.
        _strong_re = re.compile(r"(\*\*|__)(?=\S)(.+?[*_]?)(?<=\S)\1", re.S)
else:
    CustomMarkdown = None
