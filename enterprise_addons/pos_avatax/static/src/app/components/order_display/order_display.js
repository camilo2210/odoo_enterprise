import { patch } from "@web/core/utils/patch";
import { t } from "@odoo/owl";
import {
    OrderDisplay,
    orderDisplayProps,
} from "@point_of_sale/app/components/order_display/order_display";

Object.assign(orderDisplayProps, {
    refreshAvatax: t.function().optional(),
    isAvataxConfig: t.boolean().optional(),
});

patch(OrderDisplay.prototype, {
    async refreshAvatax() {
        if (!this.props.refreshAvatax) {
            return;
        }

        await this.props.refreshAvatax();
    },
});
