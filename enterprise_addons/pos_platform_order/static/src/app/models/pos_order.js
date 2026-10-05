import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

const PLATFORM_ORDER_STATUS_MAP = Object.freeze({
    new: _t("New"),
    accepted: _t("Accepted"),
    driver_allocated: _t("Driver Allocated"),
    driver_arrived: _t("Driver Arrived"),
    collected: _t("Collected"),
    delivered: _t("Delivered"),
    cancelled: _t("Cancelled"),
    failed: _t("Failed"),
});

patch(PosOrder.prototype, {
    get isPlatformOrder() {
        return Boolean(this.platform_order_provider_id);
    },
    get canSetFoodReady() {
        return (
            this.isPlatformOrder &&
            ["accepted", "driver_allocated", "driver_arrived"].includes(this.platform_order_status)
        );
    },
    get finalized() {
        const isPlatformOrderFinalized =
            this.isPlatformOrder &&
            ["delivered", "cancelled", "failed"].includes(this.platform_order_status);
        return super.finalized || isPlatformOrderFinalized;
    },
    get platformOrderStatus() {
        if (!this.isPlatformOrder) {
            return "";
        }
        return PLATFORM_ORDER_STATUS_MAP[this.platform_order_status] || _t("Unknown");
    },
    get orderStatusClass() {
        if (!this.isPlatformOrder) {
            return "";
        }
        switch (this.platform_order_status) {
            case "new":
                return "bg-warning text-white";
            case "accepted":
                return "bg-primary text-white";
            case "driver_allocated":
            case "driver_arrived":
                return "bg-light";
            case "collected":
            case "delivered":
                return "bg-success text-white";
            case "cancelled":
            case "failed":
                return "bg-danger text-white";
            default:
                return "";
        }
    },
    get rejectReasonOptions() {
        return [];
    },
});
