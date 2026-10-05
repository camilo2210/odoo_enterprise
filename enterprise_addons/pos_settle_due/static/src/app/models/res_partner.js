import { ResPartner } from "@point_of_sale/app/models/res_partner";
import { patch } from "@web/core/utils/patch";

patch(ResPartner.prototype, {
    get creditLimit() {
        return this.credit_limit || 0;
    },
    get overDue() {
        const openOrders = this.models["pos.order"].filter((o) => o.partner_id?.id === this.id);
        const cartValue = openOrders.reduce((acc, o) => acc + o.priceIncl, 0);
        const limit = this.creditLimit;
        return cartValue + this.total_due > limit;
    },
    get useLimit() {
        return this.company.account_use_credit_limit && this.creditLimit > 0 && this.overDue;
    },
    get totalDue() {
        return this.total_due + this.invoices_amount_due;
    },
});
