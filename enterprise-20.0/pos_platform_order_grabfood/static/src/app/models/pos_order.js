import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PosOrder.prototype, {
    get rejectReasonOptions() {
        if (this.platform_order_provider_code === "grabfood") {
            return [
                { id: "1001", label: _t("Items Unavailable"), item: "1001" },
                { id: "1002", label: _t("Too Busy"), item: "1002" },
                { id: "1003", label: _t("Shop Closed"), item: "1003" },
                { id: "1004", label: _t("Shop Closing Soon"), item: "1004" },
            ];
        }
        return super.rejectReasonOptions;
    },
});
