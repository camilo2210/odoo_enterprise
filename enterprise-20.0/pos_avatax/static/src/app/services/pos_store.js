import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    async getAvataxTaxesRpc() {
        if (!this.config.module_pos_avatax) {
            return;
        }

        try {
            const order = this.getOrder();
            if (this.env.services.ui.isBlocked) {
                return;
            } else {
                this.env.services.ui.block({ message: _t("Updating Avatax taxes...") });
            }

            const serialized = order.serializeForORM();
            const context = this.getSyncAllOrdersContext([order]);
            const data = await this.data.call(
                "pos.order",
                "get_order_tax_details",
                [[serialized]],
                { context }
            );
            const missingRecords = await this.data.missingRecursive(data);
            this.models.loadConnectedData(missingRecords);
        } catch (e) {
            this.dialog.add(AlertDialog, {
                title: _t("Error while loading Avatax taxes"),
                body:
                    e?.data?.message ||
                    _t("Unable to load Avatax taxes, please verify Avatax API configuration."),
            });
            console.error(e);
        } finally {
            this.env.services.ui.unblock();
        }
    },
});
