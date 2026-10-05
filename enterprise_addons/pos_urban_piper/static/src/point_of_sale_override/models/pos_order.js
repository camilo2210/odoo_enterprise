import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { getTime, URBANPIPER_ORDER_STATUS } from "@pos_urban_piper/utils";

patch(PosOrder.prototype, {
    initState() {
        super.initState();
        this.uiState = {
            ...this.uiState,
            orderAcceptTime: 0,
        };
    },

    get isDeliveryOrder() {
        return this.source === "online" && this.delivery_identifier;
    },

    get deliveryJson() {
        return JSON.parse(this.delivery_json || "{}");
    },

    get extPlatform() {
        return this.deliveryJson.order?.details?.ext_platforms?.[0] || {};
    },

    get deliveryTime() {
        return getTime(this.deliveryJson.order?.details?.delivery_datetime);
    },

    get deliveryStatusStr() {
        return URBANPIPER_ORDER_STATUS[this.delivery_status] || "";
    },

    getDeliveryProviderName() {
        return this.delivery_provider_id?.name || "";
    },

    getOrderStatus() {
        return this.delivery_status || "";
    },

    get isDirectSale() {
        return Boolean(super.isDirectSale && !this.isDeliveryOrder);
    },

    get deliveryOrderType() {
        return this.extPlatform?.delivery_type || "";
    },

    get isFutureOrder() {
        return this.isDeliveryOrder && Boolean(this.preset_time);
    },

    get providerOrderId() {
        return this.extPlatform?.id || "";
    },

    get deliveryOtp() {
        return this.extPlatform?.extras?.order_otp || "";
    },

    get isInstantOrder() {
        return this.extPlatform?.extras?.is_instant_order ?? false;
    },

    get deliveryCustomerData() {
        const customerJson = this.deliveryJson.customer;
        const addressJson = customerJson?.address;
        return {
            name: customerJson?.name || "",
            phone: customerJson?.phone || "",
            email: customerJson?.email || "",
            address: addressJson
                ? [addressJson.line_1, addressJson.line_2, addressJson.city, addressJson.pin]
                      .filter(Boolean)
                      .join(", ")
                : "",
            addressJson: addressJson || {},
        };
    },
});
