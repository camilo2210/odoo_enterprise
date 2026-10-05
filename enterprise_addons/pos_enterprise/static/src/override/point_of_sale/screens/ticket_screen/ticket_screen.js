import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    setup() {
        super.setup();
        this.state.isPlatformFilterActive = false;
    },

    shouldShowPlatformFilterButton() {
        return false;
    },

    togglePlatformFilter() {
        this.state.isPlatformFilterActive = !this.state.isPlatformFilterActive;

        if (this.state.isPlatformFilterActive) {
            this.state.selectedPreset = null;
        }

        const firstFilteredOrder = this.getFilteredOrderList()[0];
        firstFilteredOrder && this.onClickOrder(firstFilteredOrder);
    },

    onPresetSelected(preset) {
        if (this.state.isPlatformFilterActive) {
            this.state.isPlatformFilterActive = false;
        }
        return super.onPresetSelected(...arguments);
    },

    getFilteredOrderList() {
        const orders = super.getFilteredOrderList();
        if (!this.state.isPlatformFilterActive) {
            return orders;
        }
        return orders.filter(
            (order) => order.delivery_identifier || order.platform_order_provider_id
        );
    },
});
