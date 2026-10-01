import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { patch } from "@web/core/utils/patch";

patch(OrderSummary.prototype, {
    async updateSelectedOrderline({ buffer, key }) {
        const updatedLine = await super.updateSelectedOrderline({ buffer, key });
        const order = this.pos.getOrder();
        // cancel the transaction if last line is removed
        if (this.pos.isCountryGermanyAndFiskaly() && !order.lines.length) {
            await this.pos.handleFiskalyCancellation(order);
        }
        return updatedLine;
    },
});
