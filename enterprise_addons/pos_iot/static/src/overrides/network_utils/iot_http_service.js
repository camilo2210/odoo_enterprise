import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { iotHttpService, IotHttpService } from "@iot/network_utils/iot_http_service";
import { session } from "@web/session";

patch(iotHttpService, {
    dependencies: [...iotHttpService.dependencies, "dialog"].filter(
        (dep) => dep !== "lazy_session"
    ),
});

patch(IotHttpService.prototype, {
    setup({ dialog }) {
        super.setup(...arguments);
        this.dialog = dialog;

        // Since the POS already handles LNA init, we don't do it in the IoT service
        this.lnaInitialised = true;
    },

    async _longpolling() {
        try {
            return await super._longpolling(...arguments);
        } catch (error) {
            const isKiosk = session.data?.self_ordering_mode === "kiosk";
            if (error.message.includes("Longpolling RPC Error") && !isKiosk) {
                this.dialog.add(AlertDialog, {
                    title: _t("IoT Box Warning"),
                    body: _t(`It seems that your POS cannot contact your IOT through the local network. The POS will fallback with web socket connection.
You can check if all your connected devices are connected to the same network as the IoT Box.
If the problem persists, consult the documentation or contact our support.`),
                });
            }
            throw error;
        }
    },
});
