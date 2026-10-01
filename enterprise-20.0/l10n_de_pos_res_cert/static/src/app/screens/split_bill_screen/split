import { SplitBillScreen } from "@pos_restaurant/app/screens/split_bill_screen/split_bill_screen";
import { patch } from "@web/core/utils/patch";

patch(SplitBillScreen.prototype, {
    async _createNewSplitOrder(originalOrder, newOrderName, curOrderUuid) {
        const newOrder = await super._createNewSplitOrder(...arguments);
        if (this.pos.isRestaurantCountryGermanyAndFiskaly()) {
            this.pos.addPendingOrder([originalOrder.id, newOrder.id]);
        }
        return newOrder;
    },
});
