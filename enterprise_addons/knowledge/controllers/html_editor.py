from urllib.parse import urlparse

from odoo import http
from odoo.http import request

from odoo.addons.html_editor.controllers.main import HTML_Editor


class HtmlEditorController(HTML_Editor):
    @http.route()
    def link_preview_metadata_internal(self, preview_url):
        """
        Override the default link preview to handle /knowledge/ URLs differently.
        """
        parsed_preview_url = urlparse(preview_url)
        path_segments = parsed_preview_url.path.strip('/').split('/')

        # Check for URL patterns like /knowledge/article/<id> or */knowledge/<id>.
        last_segment = path_segments.pop() if path_segments else ''
        if (last_segment.isnumeric()
            and (
                    (parsed_preview_url.path.startswith("/odoo") and path_segments[-1] == "knowledge")  # */knowledge/<id>
                 or (len(path_segments) == 2 and path_segments[-2] == "knowledge" and path_segments[-1] == "article")  # /knowledge/article/<id>
            )
        ):
            article = request.env["knowledge.article"].browse(int(last_segment)).exists()

            if article:
                return {
                    "description": article.summary,
                    "preview_image_url": article.cover_image_url,
                    "display_name": article.display_name,
                }

        return super().link_preview_metadata_internal(preview_url)
