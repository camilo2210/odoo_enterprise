from odoo import models
from odoo.addons.mail.tools.discuss import Store


class ResCountry(models.Model):
    _inherit = "res.country"

    def _get_country_by_country_code(self, country_code):
        country = self.search([("code", "=ilike", country_code)], limit=1)
        store = Store().add(country, "_store_voip_fields")
        return {"countryId": country.id, "storeData": store}

    def _store_voip_fields(self, res: Store.FieldList):
        res.extend(["code", "image_url", "name", "phone_code"])
