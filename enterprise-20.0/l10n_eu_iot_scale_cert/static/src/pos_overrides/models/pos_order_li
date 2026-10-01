import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { formatFloat } from "@web/core/utils/numbers";
import { patch } from "@web/core/utils/patch";

patch(PosOrderline.prototype, {
    initState() {
        super.initState();
        this.uiState = {
            ...this.uiState,
            isDeleted: false,
            deletedWeightQuantityStr: null,
            deletedWeightPriceStr: null,
        };
    },

    get quantityStr() {
        if (this.uiState.deletedWeightQuantityStr) {
            return this.uiState.deletedWeightQuantityStr;
        }
        const superResult = super.quantityStr;
        const unit = this.product_id.uom_id;
        if (this.config.isCertified) {
            const decimals = this.models["decimal.precision"].find(
                (dp) => dp.name === "Product Unit"
            ).digits;
            return {
                ...superResult,
                qtyStr: formatFloat(this.qty, {
                    digits: [69, decimals],
                    trailingZeros: unit.id !== this.config._unit_uom_id,
                }),
            };
        }

        return super.quantityStr;
    },

    get showUnit() {
        return this.product_id.uom_id.id !== this.config._unit_uom_id;
    },

    canBeMergedWith(orderline) {
        if (this.uiState.isDeleted || orderline.uiState.isDeleted) {
            return false;
        }
        return super.canBeMergedWith(orderline);
    },
});
