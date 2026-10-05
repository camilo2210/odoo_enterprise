import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@pos_enterprise/app/models/pos_order";

patch(PosOrder.prototype, {
    // Copy methods from js models of point of sale to use the same printing service for preparation.
    getDeliveryProviderName() {
        return this.delivery_provider_id?.name || "";
    },

    get deliveryOtp() {
        return this.extPlatform?.extras?.order_otp || "";
    },

    get extPlatform() {
        return this.deliveryJson.order?.details?.ext_platforms?.[0] || {};
    },

    get deliveryJson() {
        return JSON.parse(this.delivery_json || "{}");
    },
});
