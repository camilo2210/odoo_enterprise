import { DebugWidget } from "@point_of_sale/app/utils/debug/debug_widget";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(DebugWidget.prototype, {
    get showUrbanPiperTestOrderBtn() {
        return this.pos.config.urbanpiper_store_id?.delivery_provider_ids?.length;
    },

    placeUrbanPiperTestOrder() {
        const urbanpiperStore = this.pos.config.urbanpiper_store_id;
        const providerIds = urbanpiperStore.delivery_provider_ids.map((provider) => provider.id);
        this.pos.action.doAction({
            name: _t("Test Food Delivery Order"),
            type: "ir.actions.act_window",
            res_model: "pos.urbanpiper.test.order.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {
                store_id: urbanpiperStore.id,
                dialog_size: "medium",
                delivery_provider_ids: providerIds,
                default_delivery_provider_id: providerIds[0],
            },
        });
        this.toggleWidget(); // auto close debug widget
    },
});
