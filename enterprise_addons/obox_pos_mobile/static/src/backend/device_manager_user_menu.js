import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { hasMobileNative, mobileNative } from "@pos_mobile_android/app/utils/native";

export const DEVICE_MANAGER_ITEM = "obox_pos_mobile.device_manager";

export function deviceManagerItem(env) {
    return {
        type: "item",
        id: DEVICE_MANAGER_ITEM,
        description: _t("Device Manager"),
        callback: async () => {
            try {
                await mobileNative.openDeviceManager({ url: browser.location.origin });
            } catch (error) {
                console.error(error);
                env.services.notification.add(_t("Could not open the device manager"), {
                    type: "danger",
                });
            }
        },
        sequence: 99,
    };
}

if (hasMobileNative("openDeviceManager")) {
    registry.category("user_menuitems").add(DEVICE_MANAGER_ITEM, deviceManagerItem);
}
