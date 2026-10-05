import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(PaymentScreen.prototype, {
    /**
     * @override
     */
    setup() {
        super.setup();
        if (this.currentOrder.refunded_order_id?.isDeliveryOrder) {
            const aggregatorLines = this.pos.config.urbanpiper_store_id?.aggregator_lines || [];
            this.payment_methods_from_config = [
                ...this.payment_methods_from_config,
                ...aggregatorLines.map((aggregator) => aggregator.payment_method_id),
            ];
        }
    },
});
