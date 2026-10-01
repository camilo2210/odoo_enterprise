from odoo import models

from odoo.addons.mail.tools.discuss import Store


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _store_voip_fields(self, res: Store.FieldList):
        super()._store_voip_fields(res)
        if self.has_field_access(self._fields["employees_count"], "read") and self.env["hr.employee"].has_access("read"):
            res.attr("employees_count")
