import { patch } from "@web/core/utils/patch";
import { PosPrepOrder } from "@pos_enterprise/app/models/pos_preparation_order";
import { getTime, URBANPIPER_ORDER_STATUS } from "@pos_urban_piper/utils";

patch(PosPrepOrder.prototype, {
    get isDeliveryOrder() {
        return this.order.delivery_identifier;
    },

    get isFutureOrder() {
        return this.isDeliveryOrder && Boolean(this.order.preset_time);
    },

    get deliveryJson() {
        return JSON.parse(this.order.delivery_json || "{}");
    },

    get extPlatform() {
        return this.deliveryJson.order?.details?.ext_platforms?.[0] || {};
    },

    get deliveryTime() {
        return getTime(this.deliveryJson.order?.details?.delivery_datetime);
    },

    get orderOtp() {
        return this.extPlatform?.id || "";
    },

    get deliveryStatusStr() {
        return URBANPIPER_ORDER_STATUS[this.order.delivery_status];
    },

    get isInstantOrder() {
        return this.extPlatform.extras?.is_instant_order;
    },
});
