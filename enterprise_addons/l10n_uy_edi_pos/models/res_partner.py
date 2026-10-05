from odoo import api, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ["commercial_partner_id"]

    @api.ondelete(at_uninstall=False)
    def _l10n_uy_unlink_except_master_data(self):
        final_consumer = self.env.ref("l10n_uy.partner_cfu", raise_if_not_found=False)
        if final_consumer and final_consumer & self:
            raise UserError(self.env._(
                "Deleting the partner %s is not allowed because it is required by the Uruguayan point of sale.",
                final_consumer.display_name,
            ))
