import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formView } from "@web/views/form/form_view";
import { _t } from "@web/core/l10n/translation";

class IoTDeviceController extends formView.Controller {
    setup() {
        super.setup();
        this.iotHttp = useService("iot_http");
        this.notification = useService("notification");
    }

    async onRecordSaved(record, changes) {
        if (["keyboard", "scanner"].includes(record.data.type)) {
            await this.updateKeyboardLayout(record.data);
        } else if (record.data.type === "display") {
            await this.updateDisplay(record.data, changes);
        }
    }
    /**
     * Send an action to the device to update the keyboard layout
     */
    async updateKeyboardLayout(data) {
        const { iot_id, identifier, keyboard_layout, is_scanner } = data;
        // IMPROVEMENT: Perhaps combine the call to update_is_scanner and update_layout in just one remote call to the iotbox.
        this.iotHttp.action(
            iot_id.id,
            identifier,
            {
                action: "update_is_scanner",
                is_scanner,
            },
            () => {},
            () => {
                this.notification.add(_t("Failed to update scanner mode on the device."), {
                    type: "danger",
                });
            }
        );
        if (keyboard_layout) {
            const [keyboard] = await this.model.orm.read(
                "iot.keyboard.layout",
                [keyboard_layout.id],
                ["layout", "variant"]
            );
            return this.iotHttp.action(
                iot_id.id,
                identifier,
                {
                    action: "update_layout",
                    layout: keyboard.layout,
                    variant: keyboard.variant,
                },
                () => {},
                () => {
                    this.notification.add(_t("Failed to update keyboard layout on the device."), {
                        type: "danger",
                    });
                }
            );
        } else {
            return this.iotHttp.action(iot_id.id, identifier, { action: "update_layout" });
        }
    }
    /**
     * Send an action to the device to update the screen url
     */
    async updateDisplay(data, changes) {
        const { iot_id, identifier, display_url, display_orientation } = data;
        if ("display_url" in changes) {
            this.iotHttp.action(iot_id.id, identifier, {
                action: "update_url",
                url: display_url,
            });
        }
        if ("display_orientation" in changes) {
            this.iotHttp.action(
                iot_id.id,
                identifier,
                {
                    action: "rotate_screen",
                    orientation: display_orientation,
                },
                () =>
                    this.notification.add(_t("Display settings updated."), {
                        type: "success",
                    })
            );
        }
    }
}

export const iotDeviceFormView = {
    ...formView,
    Controller: IoTDeviceController,
};

registry.category("views").add("iot_device_form", iotDeviceFormView);
