import { onMounted, onWillUnmount, proxy } from "@odoo/owl";
import { useLayoutEffect } from "@web/owl2/utils";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { ProviderLogo } from "./provider_logo";
const { DateTime } = luxon;

const MS_PER_SEC = 1000;

patch(TicketScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.state = proxy({
            ...this.state,
            currentTime: DateTime.now(),
        });

        let interval;
        onMounted(() => {
            interval = setInterval(() => {
                this.state.currentTime = DateTime.now();
            }, MS_PER_SEC);
        });
        onWillUnmount(() => clearInterval(interval));

        useLayoutEffect(
            () => {
                if (this.pos.selectedOrderUuid) {
                    this.state.selectedOrderUuid = this.pos.selectedOrderUuid;
                }
            },
            () => [this.pos.selectedOrderUuid]
        );
    },

    shouldShowPlatformFilterButton() {
        return this.pos.config._has_platform_order_entity
            ? true
            : super.shouldShowPlatformFilterButton();
    },

    // =========================================================================
    // EVENT HANDLERS
    // =========================================================================

    onDblClickOrder(order) {
        if (order.isPlatformOrder) {
            return;
        }
        super.onDblClickOrder(...arguments);
    },

    async onMarkFoodReadyClicked(order) {
        const rpcCall = this.pos.data.call("pos.order", "platform_order_status_update_from_ui", [
            order.id,
            "food_ready",
        ]);
        const result = await this._handleRpc(order, rpcCall);
        if (result.success) {
            order.platform_order_food_ready = true;
        }
    },

    async onAcceptOrderClicked(order) {
        const rpcCall = this.pos.data.call("pos.order", "platform_order_status_update_from_ui", [
            order.id,
            "accept",
        ]);
        await this._handleRpc(order, rpcCall, { block: true });
    },

    // =========================================================================
    // GETTERS (COMPUTED PROPERTIES)
    // =========================================================================

    get showAcceptOrderButton() {
        const order = this.getSelectedOrder();
        return order?.isPlatformOrder && order.platform_order_status === "new";
    },

    get selectedOrderExpiration() {
        const order = this.getSelectedOrder();
        if (!order?.isPlatformOrder || !order.platform_order_provider_id.valid_for_seconds) {
            return false;
        }

        const expirationMs = order.platform_order_provider_id.valid_for_seconds * MS_PER_SEC;
        const orderTime = DateTime.fromISO(order.create_date);
        const timeDiffMs = this.state.currentTime.diff(orderTime).toMillis();
        const remainingMs = Math.max(0, expirationMs - timeDiffMs);

        return {
            isExpired: remainingMs === 0,
            formattedRemainingTime: DateTime.fromMillis(remainingMs).toFormat("mm:ss"),
            remainingTimePercentage: (remainingMs / expirationMs) * 100,
        };
    },

    // =========================================================================
    // FILTERING LOGIC
    // =========================================================================
    isOrderDoneOrPaid(order) {
        if (order.isPlatformOrder) {
            return order.platform_order_status === "delivered";
        }
        return super.isOrderDoneOrPaid(...arguments);
    },
    isOrderCancelled(order) {
        if (order.isPlatformOrder) {
            return ["cancelled", "failed"].includes(order.platform_order_status);
        }
        return super.isOrderCancelled(...arguments);
    },

    /** @override */
    getStatus(order) {
        if (!order.isPlatformOrder) {
            return super.getStatus(...arguments);
        }

        const statusMap = {
            new: _t("New"),
            accepted: _t("Ongoing"),
            collected: _t("Paid"),
            delivered: _t("Paid"),
            cancelled: _t("Cancelled"),
            failed: _t("Failed"),
        };
        return statusMap[order.platform_order_status] || "";
    },

    /** @override */
    getStatusDecoration(status) {
        if (status === "New") {
            return "info";
        }
        if (status === "Failed") {
            return "danger";
        }
        return super.getStatusDecoration(...arguments);
    },

    // =========================================================================
    // PRIVATE HELPERS
    // =========================================================================

    async _handleRpc(order, rpcPromise, { block = false } = {}) {
        if (block) {
            this.ui.block();
        }
        try {
            const result = await rpcPromise;
            if (!result.success) {
                this.pos.notification.add(result.message, {
                    type: "danger",
                    title: _t("Order Reference: %s", order.platform_order_ref),
                });
            }
            return result;
        } catch (error) {
            logPosMessage("TicketScreen", "_handleRpc", "Error occurred", false, [error]);

            let message = _t("An unknown error occurred.");
            if (!navigator.onLine) {
                message = _t("Device is offline. Platform order requires an internet connection.");
            }

            this.pos.notification.add(message, {
                type: "danger",
                title: _t("Order Reference: %s", order.platform_order_ref),
            });
            return { success: false, message: _t("Unknown error") };
        } finally {
            if (block) {
                this.ui.unblock();
            }
        }
    },
});

patch(TicketScreen, {
    components: { ...TicketScreen.components, ProviderLogo },
});
