import { proxy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { useService } from "@web/core/utils/hooks";
import { getOnNotified } from "@point_of_sale/utils";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { computeDurationSinceDate } from "@pos_enterprise/app/utils/utils";
import { rpc } from "@web/core/network/rpc";

const orderTrackingDisplayService = {
    dependencies: ["bus_service"],
    async start(env, { bus_service }) {
        const orders = proxy(session.initial_data);
        const onNotified = getOnNotified(bus_service, session.preparation_display.access_token);
        onNotified("NEW_ORDERS", () => {
            rpc("/pos-order-tracking/get_orders", {
                id: session.preparation_display.id,
                access_token: session.preparation_display.access_token,
            }).then((data) => {
                Object.assign(orders, data.orders);
            });
        });
        if (session.preparation_display.auto_clear) {
            this.interval = setInterval(() => {
                this._clearOutdatedOrder(orders);
            }, 10000);
        }
        return orders;
    },
    _clearOutdatedOrder(orders) {
        orders.done = orders.done.filter((order) => {
            const duration = computeDurationSinceDate(
                deserializeDateTime(orders.ordersCompletedReadyDate[order])
            );
            return duration < session.preparation_display.clear_time_interval;
        });
    },
};

registry.category("services").add("order_tracking_display", orderTrackingDisplayService);
export function useOrderStatusDisplay() {
    return useService("order_tracking_display");
}
