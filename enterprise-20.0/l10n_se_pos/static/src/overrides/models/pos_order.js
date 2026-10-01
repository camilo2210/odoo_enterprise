import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    useBlackBoxSweden() {
        return !!this.config.iot_fdm_se_id;
    },
    getSpecificTax(category) {
        const tax = this.prices.taxDetails.subtotals[0].tax_groups.find(
            (tax) => tax.group_label === category
        );

        if (tax) {
            return tax.tax_amount;
        }

        return false;
    },
    waitForPushOrder() {
        let result = super.waitForPushOrder(...arguments);
        result = Boolean(this.useBlackBoxSweden() || result);
        return result;
    },
    get seType() {
        if (this.isReprint) {
            return "COPY";
        } else if (this.isProfo) {
            return "PRO FORMA";
        } else {
            return (this.amount_total < 0 ? "return" : "") + "receipt";
        }
    },
});
