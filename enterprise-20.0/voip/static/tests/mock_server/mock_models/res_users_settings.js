import { mailModels } from "@mail/../tests/mail_test_helpers";

export class ResUsersSettings extends mailModels.ResUsersSettings {
    _store_settings_fields(res) {
        super._store_settings_fields(res);
        res.extend([
            "do_not_disturb_until_dt",
            "external_device_number",
            "how_to_call_on_mobile",
            "should_call_from_another_device",
            "voip_secret",
            "voip_username",
        ]);
    }
}
