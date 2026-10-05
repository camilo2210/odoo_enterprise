import { ProductTemplate } from "@point_of_sale/app/models/product_template";
import { patch } from "@web/core/utils/patch";

patch(ProductTemplate.prototype, {
    isAvailableForFoodDelivery(storeId) {
        return this.raw.urbanpiper_store_ids.includes(storeId);
    },
    setFoodDeliveryAvailability(status, storeId) {
        let availableStoreIds = [...this.raw.urbanpiper_store_ids, storeId];
        if (!status) {
            availableStoreIds = availableStoreIds.filter((id) => id !== storeId);
        }
        this.update({
            urbanpiper_store_ids: availableStoreIds,
        });
    },
});
