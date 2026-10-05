# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.web.controllers.home import Home


class SocialHome(Home):
    def _get_allowed_robots_routes(self):
        """Sometimes crawler allowance is needed for it to properly download the image from our url."""
        return super()._get_allowed_robots_routes() + ["/social/download_attachment"]
