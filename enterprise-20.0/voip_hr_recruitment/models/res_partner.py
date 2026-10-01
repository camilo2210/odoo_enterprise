from odoo import models
from odoo.exceptions import AccessError

from odoo.addons.mail.tools.discuss import Store


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _store_voip_fields(self, res: Store.FieldList):
        super()._store_voip_fields(res)

        def can_read_applicant_ids(partner):
            try:
                partner.fetch(["applicant_ids"])
            except AccessError:
                return False
            return True

        res.many("applicant_ids", ["partner_id", "partner_name"], predicate=can_read_applicant_ids)
