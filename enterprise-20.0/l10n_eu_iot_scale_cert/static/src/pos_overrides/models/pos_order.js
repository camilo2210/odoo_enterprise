import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    get showCertificationWarning() {
        return this.config.showCertificationWarning;
    },

    isEmpty() {
        return super.isEmpty() || this.lines.every((line) => line.uiState.isDeleted);
    },
});
