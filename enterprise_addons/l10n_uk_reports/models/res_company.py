from odoo import fields, models


NORTHERN_IRISH_STATES_XML_IDS = {'base.state_uk' + str(i) for i in range(18, 25)}


class ResCompany(models.Model):
    _inherit = "res.company"

    def is_northern_irish(self):
        if self.country_id.code == "XI":
            return True
        if not self.state_id:
            return False
        state_xml_id = self.state_id._get_external_ids()[self.state_id.id]
        return bool(NORTHERN_IRISH_STATES_XML_IDS.intersection(state_xml_id))

    l10n_uk_user_token = fields.Char(string='IAP HMRC User Token', copy=False, groups="base.group_system")
    l10n_uk_hmrc_vat_token = fields.Char(string='HMRC VAT Token', copy=False, groups="base.group_system")
    l10n_uk_hmrc_vat_token_expiration_time = fields.Datetime(string='HMRC Token Expiration Time', copy=False, groups="base.group_system")
