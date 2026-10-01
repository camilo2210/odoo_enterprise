import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

patch(TicketScreen.prototype, {
    async postRefund(destinationOrder) {
        await super.postRefund(...arguments);
        if (
            this.pos.isCountryGermanyAndFiskaly() &&
            !destinationOrder.config.module_pos_restaurant
        ) {
            try {
                await this.pos.createTransaction(destinationOrder);
            } catch (error) {
                this.pos.fiskalyError(error);
            }
        }
    },
});
