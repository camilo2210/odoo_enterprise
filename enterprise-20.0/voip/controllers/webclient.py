from odoo.http import request
from odoo.addons.mail.controllers.webclient import WebclientController
from odoo.addons.mail.tools.discuss import Store
from odoo.addons.mail.tools.store_handler import store_handler


class WebClient(WebclientController):
    @store_handler("res.country", audience="everyone")
    def store_get_res_country(self, store: Store):
        ResCountry = request.env["res.country"]
        store.add(ResCountry.search([("phone_code", "!=", False)], order="name"), "_store_voip_fields")
