import { DebugWidget } from "@point_of_sale/app/utils/debug/debug_widget";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { IotTestDialog } from "../iot_test_dialog/iot_test_dialog";

patch(DebugWidget.prototype, {
    async testIotBoxes() {
        const iotDevices = this.pos.config.iot_device_ids;
        if (iotDevices.length === 0) {
            this.notification.add(_t("No IoT devices are configured in this POS."), {
                type: "warning",
            });
            return;
        }

        this.dialog.add(IotTestDialog, {
            iotDevices,
        });
    },
});
