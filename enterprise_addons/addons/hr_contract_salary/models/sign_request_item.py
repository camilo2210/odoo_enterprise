from odoo import api, models


class SignRequestItem(models.Model):
    _inherit = 'sign.request.item'

    def _get_auto_field_custom_value(self, field_record_sudo=None, item_type_sudo=None, record=None, auto_value=''):
        """ Override to retrieve automatic value following other logic for specific models"""
        self.ensure_one()
        auto_field = item_type_sudo.auto_field
        auto_value = super()._get_auto_field_custom_value(
            field_record_sudo=field_record_sudo,
            item_type_sudo=item_type_sudo,
            record=record,
            auto_value=auto_value
        )
        if record._name == 'hr.version':
            # This override is done here to avoid creating bridge module for this.
            auto_value = self._get_vehicule_auto_value(auto_value, record, auto_field, vehicule="car")
            auto_value = self._get_vehicule_auto_value(auto_value, record, auto_field, vehicule="bike")
            if auto_field == 'l10n_be_group_insurance_rate':
                auto_value = 1 if record.l10n_be_group_insurance_rate else 0
            elif auto_field == 'ip_value':
                auto_value = round(record.ip_value * 100, 2) if record.ip_wage_rate > 0 else 0
        return auto_value

    @api.model
    def _get_vehicule_auto_value(self, auto_value, version, auto_field, vehicule=""):
        # get field name depending on the vehicule
        assert (vehicule in ['car', 'bike'])
        transport = f"transport_mode_{vehicule}"
        is_new = f"new_{vehicule}"
        new_vehicule = f"new_{vehicule}_model_id"
        exiting_vehicule = f"{vehicule}_id"
        if auto_field == transport and transport in version and version[transport]:
            # Fleet is installed. We transform the boolean transport into the model name to avoid
            # creating a computed field to fallback either on {vehicule}_id.model_id or new_{vehicule}_model_id
            if not version[is_new] and version[exiting_vehicule]:
                auto_value = version[exiting_vehicule].name
            elif vehicule[is_new] and version[new_vehicule]:
                auto_value = version[new_vehicule].name
        return auto_value
