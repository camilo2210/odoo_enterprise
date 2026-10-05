import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        const result = await super.addNewPaymentLine(...arguments);
        // will start the receipt txn when first payment line added for restaurant orders
        if (
            result &&
            !this.pos.data.network.offline &&
            this.pos.isRestaurantCountryGermanyAndFiskaly() &&
            this.currentOrder.isReceiptInactive
        ) {
            try {
                await this.pos.createTransaction(this.currentOrder);
            } catch (error) {
                this.pos.fiskalyError(error);
            }
        }
        return result;
    },
});
