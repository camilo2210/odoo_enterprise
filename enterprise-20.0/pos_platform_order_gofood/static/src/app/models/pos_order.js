import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PosOrder.prototype, {
    get rejectReasonOptions() {
        if (this.platform_order_provider_code === "gofood") {
            return [
                { id: "HIGH_DEMAND", label: _t("High Demand"), item: "HIGH_DEMAND" },
                {
                    id: "RESTAURANT_CLOSED",
                    label: _t("Restaurant Closed"),
                    item: "RESTAURANT_CLOSED",
                },
                {
                    id: "ITEMS_OUT_OF_STOCK",
                    label: _t("Items Out of Stock"),
                    item: "ITEMS_OUT_OF_STOCK",
                },
                { id: "OTHERS", label: _t("Others"), item: "OTHERS" },
            ];
        }
        return super.rejectReasonOptions;
    },
});
