import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    //@Override
    setup() {
        super.setup(...arguments);
        if (this.pos.isCountryGermanyAndFiskaly()) {
            this.pos.validateOrderFree = true;
        }
    },
});
