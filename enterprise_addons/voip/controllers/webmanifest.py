from odoo.http import request
from odoo.tools import file_open
from odoo.addons.web.controllers import webmanifest


class WebManifest(webmanifest.WebManifest):

    def _get_service_worker_content(self):
        body = super()._get_service_worker_content()

        # Add notification support to the service worker if user but no public
        if request.env.user._is_internal():
            with file_open("voip/static/src/service_worker.js") as f:
                body += f.read()

        return body
