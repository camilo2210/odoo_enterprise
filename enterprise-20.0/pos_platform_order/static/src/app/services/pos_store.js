import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ask, makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";
import { Domain } from "@web/core/domain";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);

        this.data.connectWebSocket("PLATFORM_ORDER_SYNCHRONISATION", ({ order_id, is_new_order }) =>
            this._fetchPlatformOrder(order_id, is_new_order)
        );
    },

    async _fetchPlatformOrder(order_id, is_new_order) {
        const lastOrderStatus = this.models["pos.order"].get(order_id)?.platform_order_status;
        try {
            await this.getServerOrder(order_id);
        } catch (error) {
            let message;
            let details = "";

            if (!navigator.onLine) {
                message = _t("Device is offline. Platform order requires an internet connection.");
            } else {
                message = _t("Server Error: Unable to fetch order.");
                logPosMessage(
                    "POS Store",
                    "_fetchPlatformOrder",
                    "Failed to fetch platform order from server",
                    false,
                    [error]
                );
                if (error?.message?.data?.message) {
                    details = error.message.data.message;
                }
            }

            this.notification.add(message, { type: "warning", sticky: false });

            if (details) {
                this.notification.add(details, { type: "danger", sticky: true });
            }

            return;
        }

        const order = this.models["pos.order"].get(order_id);
        if (!order) {
            return;
        }
        // Only new or accepted or cancelled orders trigger UI changes
        if (!is_new_order && !["accepted", "cancelled"].includes(order.platform_order_status)) {
            return;
        }

        let isReadyToPrint = false;
        if (["accepted", "cancelled"].includes(order.platform_order_status)) {
            try {
                isReadyToPrint = await this.data.callRelated(
                    "pos.order",
                    "mark_platform_prep_order_as_printed",
                    [order_id]
                );
            } catch {
                // do nothing
            }
        }

        if (isReadyToPrint && (is_new_order || order.platform_order_status === "accepted")) {
            await this.sendOrderInPreparationUpdateLastChange(order);
        }
        if (is_new_order) {
            this._displayNewPlatformOrderNotification(order);
        } else if (order.platform_order_status === "cancelled") {
            if (order.uuid === this.selectedOrderUuid) {
                this.selectedOrderUuid = null;
            }
            if (isReadyToPrint) {
                await this.deleteOrders([order], [], lastOrderStatus === "new");
            }
        }
    },

    // =========================================================================
    // DATA FETCHING
    // =========================================================================
    /** @override */
    getServerOrdersDomain() {
        return Domain.or([
            super.getServerOrdersDomain(),
            new Domain([
                ["config_id", "in", [...this.config.raw.trusted_config_ids, this.config.id]],
                ["platform_order_provider_id", "!=", false],
            ]),
        ]);
    },

    async getServerOrder(order_id) {
        await this.syncAllOrders();
        const domain = new Domain([
            ["config_id", "in", [...this.config.raw.trusted_config_ids, this.config.id]],
            ["id", "=", order_id],
        ]);
        return this.data.loadServerOrders(domain.toList());
    },

    // =========================================================================
    // ORDER WORKFLOW
    // =========================================================================

    /** @override */
    async beforeDeleteOrder(order, options) {
        if (!order.isPlatformOrder) {
            return super.beforeDeleteOrder(...arguments);
        }

        const isConfirmed = await ask(this.dialog, {
            title: _t("Reject Order"),
            body: _t(
                "Order %s has a total of %s. Are you sure you want to reject it?",
                order.pos_reference,
                this.formatCurrency(order.priceIncl)
            ),
        });

        if (!isConfirmed) {
            return false;
        }

        let selectedReason = null;
        const rejectOptions = order.rejectReasonOptions;
        if (rejectOptions.length > 0) {
            selectedReason = await makeAwaitable(this.dialog, SelectionPopup, {
                title: _t("Reject reason"),
                list: rejectOptions,
            });

            if (!selectedReason) {
                return false;
            }
        }
        return this._rejectOrder(order, selectedReason);
    },

    async _rejectOrder(order, reason) {
        if (order.isPlatformOrder) {
            try {
                await this.data.callRelated("pos.order", "mark_platform_prep_order_as_printed", [
                    [order.id],
                ]);
            } catch {
                // do nothing
            }
            const rpcCall = this.data.call(
                "pos.order",
                "platform_order_status_update_from_ui",
                [order.id, "reject"],
                { reason }
            );
            await this._handleRpc(order, rpcCall, {
                successMessage: _t("Order rejected successfully."),
                errorMessage: _t(
                    "Failed to reject order. Please reject the order manually from the %s terminal.",
                    order.platform_order_provider_id.name
                ),
            });
        }
        if (order.uuid === this.selectedOrderUuid) {
            this.selectedOrderUuid = null;
        }
        // Always return true to ensure the order is removed from the POS UI,
        // regardless of the server's response.
        return true;
    },

    async deleteOrders(orders, serverIds = [], ignoreChange = false) {
        const hasPlatformOrders = orders.some((order) => order.isPlatformOrder);
        if (!hasPlatformOrders) {
            return super.deleteOrders(orders, serverIds, ignoreChange);
        }

        const newOrders = [];
        const otherOrders = [];

        for (const order of orders) {
            if (order.isPlatformOrder) {
                if (order.platform_order_status === "new") {
                    newOrders.push(order);
                } else {
                    otherOrders.push(order);
                }
            } else {
                otherOrders.push(order);
            }
        }

        return Promise.allSettled([
            super.deleteOrders(newOrders, serverIds, true),
            super.deleteOrders(otherOrders, serverIds, ignoreChange),
        ]);
    },

    // =========================================================================
    // UI & NOTIFICATIONS
    // =========================================================================

    _displayNewPlatformOrderNotification(order) {
        const closeFn = this.notification.add(_t("New platform order received."), {
            type: "success",
            sticky: true,
            buttons: [
                {
                    name: _t("Review Orders"),
                    onClick: () => {
                        closeFn?.();
                        this._navigateToOrder(order.uuid);
                    },
                },
            ],
        });
    },

    _navigateToOrder(orderUuid) {
        if (this.router.currentScreen() === "TicketScreen") {
            this.selectedOrderUuid = orderUuid;
        } else {
            this.navigate("TicketScreen", { stateOverride: { selectedOrderUuid: orderUuid } });
        }
    },

    // =========================================================================
    // PRIVATE HELPERS
    // =========================================================================

    async _handleRpc(order, rpcPromise, { block = false, successMessage, errorMessage } = {}) {
        if (block) {
            this.ui.block();
        }
        try {
            const result = await rpcPromise;
            const message = result.success
                ? successMessage || result.message
                : errorMessage || result.message;
            if (message) {
                this.notification.add(message, {
                    type: result.success ? "success" : "danger",
                    title: _t("Order Reference: %s", order.platform_order_ref),
                });
            }
            return result;
        } catch (error) {
            logPosMessage("POS Store", "_handleRpc", "Error occurred", false, [error]);

            const message = !navigator.onLine
                ? _t("Device is offline. Platform order requires an internet connection.")
                : errorMessage || _t("An unknown error occurred.");

            this.notification.add(message, {
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
