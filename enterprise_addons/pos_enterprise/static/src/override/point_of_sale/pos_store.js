import { patch } from "@web/core/utils/patch";
import { CONSOLE_COLOR, PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";

patch(PosStore.prototype, {
    async sendOrderInPreparation(o, opts = {}) {
        const result = await super.sendOrderInPreparation(o, opts);
        if (this.config.preparationDisplayCategories.size > 0) {
            try {
                await this.syncAllOrders({
                    orders: [o],
                    force: true,
                    context: {
                        preparation: true,
                        silent: opts.byPassPrint,
                    },
                });
                o.updateSavedQuantity();
            } catch (error) {
                logPosMessage(
                    "Store",
                    "sendOrderInPreparation",
                    "Error while sending order to preparation display",
                    CONSOLE_COLOR,
                    [error]
                );

                // Show error popup only if warningTriggered is false
                if (!this.data.network.warningTriggered) {
                    this.dialog.add(AlertDialog, {
                        title: _t("Send failed"),
                        body: _t("Failed in sending the changes to preparation display"),
                    });
                }
            }
            o.uiState.noteHistory = {};
        }

        return result;
    },
});
