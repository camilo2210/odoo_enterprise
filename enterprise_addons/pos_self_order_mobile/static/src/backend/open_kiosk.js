import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { hasMobileNative, mobileNative } from "@pos_mobile_android/app/utils/native";

async function openKiosk(env, action) {
    const { kiosk_url, timezone } = action.params;
    const openNormally = () =>
        env.services.action.doAction({ type: "ir.actions.act_url", url: kiosk_url });

    if (!hasMobileNative("openKiosk")) {
        return openNormally();
    }
    const kioskMode = await new Promise((resolve) => {
        env.services.dialog.add(ConfirmationDialog, {
            title: _t("Enter kiosk mode?"),
            body: _t(
                "This device will open in fullscreen kiosk mode." +
                    "\nChoose “Open Normally” to continue without kiosk restrictions."
            ),
            confirmLabel: _t("Enter Kiosk Mode"),
            cancelLabel: _t("Open Normally"),
            confirm: () => resolve(true),
            cancel: () => resolve(false),
            dismiss: () => resolve(null),
        });
    });
    if (kioskMode === null) {
        return;
    }
    if (!kioskMode) {
        return openNormally();
    }
    try {
        await mobileNative.openKiosk({ kiosk_url, timezone });
    } catch (error) {
        console.error(error);
        env.services.notification.add(_t("Could not open the kiosk on this device"), {
            type: "danger",
        });
    }
}

registry.category("actions").add("pos_self_order_mobile.open_kiosk", openKiosk);
