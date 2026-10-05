import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { OboxActionButton } from "@obox/widgets/obox_action_button";

// Commands sent to the device without asking for a confirmation first.
const DIRECT_FUNCTIONS = ["action_sync_obox", "action_request_screenshot", "action_request_logs"];

patch(OboxActionButton.prototype, {
    get label() {
        switch (this.props.function) {
            case "action_sync_obox":
                return _t("Synchronize");
            case "action_kiosk_reload":
                return _t("Reload Page");
            case "action_kiosk_lock_screen":
                return _t("Lock Screen");
            case "action_kiosk_unlock_screen":
                return _t("Unlock Screen");
            case "action_request_screenshot":
                return _t("Request screenshot");
            case "action_request_logs":
                return _t("Request logs");
            default:
                return super.label;
        }
    },

    get confirmationSentence() {
        switch (this.props.function) {
            case "action_kiosk_lock_screen":
                return _t("Lock the screen on this device?");
            case "action_kiosk_unlock_screen":
                return _t("Unlock the screen on this device?");
            case "action_kiosk_reload":
                return _t("Reload the page on this device?");
            default:
                return super.confirmationSentence;
        }
    },

    async onClick() {
        if (!DIRECT_FUNCTIONS.includes(this.props.function)) {
            return super.onClick();
        }
        const result = await this.orm.call("obox.obox", this.props.function, [
            this.props.record.resId,
        ]);
        if (!result) {
            this.notification.add(_t("Failed to perform the action on Obox"), {
                type: "danger",
            });
            return;
        }
        await this.props.record.load();
    },
});
