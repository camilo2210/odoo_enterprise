from odoo import api, models


class OboxObox(models.Model):
    _inherit = 'obox.obox'

    @api.model
    def _load_pos_data_fields(self, config):
        return [*super()._load_pos_data_fields(config), 'local_port', 'local_address']

    def _get_obox_features(self):
        features = super()._get_obox_features()
        if self.env["pos.config"].search_count(self._get_obox_feature_pos_domain(), limit=1):
            features.append("point_of_sale")
        return features

    def _get_obox_feature_pos_domain(self):
        return []

    def _get_obox_feature_details(self, name):
        feature_detail = super()._get_obox_feature_details(name)

        if name != "point_of_sale":
            return feature_detail

        pos_configs = self.env["pos.config"].search(self._get_obox_feature_pos_domain())
        feature_detail["point_of_sale"] = [
            {
                "id": config.id,
                "name": config.name,
                "url": f"{config.get_base_url()}/pos/ui/{config.id}",
                "timezone": config.company_id.tz,
                "app": "point_of_sale",
            }
            for config in pos_configs
        ]

        return feature_detail
