import { BurgerMenuDialog } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { usePlugin } from "@odoo/owl";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

patch(BurgerMenuDialog.prototype, {
    setup() {
        super.setup();
        this.debugMode = usePlugin(DebugModePlugin);
    },
    async showRTStatus() {
        const result = await this.pos.ticketPrinter.fiscalPrinter.getRTStatus();
        if (result.success) {
            this.dialog.add(AlertDialog, {
                title: _t("RT Status"),
                body: JSON.stringify(result.addInfo, null, 4),
            });
        }
    },
});
