import { t, useEffect } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import {
    TicketScreen,
    ticketScreenProps,
} from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { OrderInfoPopup } from "@pos_urban_piper/point_of_sale_override/components/popups/order_info_popup/order_info_popup";

Object.assign(ticketScreenProps, {
    upState: t.string().optional(""),
});

const CANCELLATION_REASONS = {
    item_out_of_stock: { id: 1, item: "item_out_of_stock", label: _t("Product is out of Stock") },
    store_closed: { id: 2, item: "store_closed", label: _t("Store is Closed") },
    store_busy: { id: 3, item: "store_busy", label: _t("Store is Busy") },
    rider_not_available: {
        id: 4,
        item: "rider_not_available",
        label: _t("Rider is Not Available"),
    },
    invalid_item: { id: 5, item: "invalid_item", label: _t("Invalid Product") },
    out_of_delivery_radius: {
        id: 6,
        item: "out_of_delivery_radius",
        label: _t("Out of Delivery Radius"),
    },
    connectivity_issue: { id: 7, item: "connectivity_issue", label: _t("Connectivity Issue") },
    total_missmatch: { id: 8, item: "total_missmatch", label: _t("Total Missmatch") },
    option_out_of_stock: {
        id: 9,
        item: "option_out_of_stock",
        label: _t("Variants/Addons out of Stock"),
    },
    invalid_option: { id: 10, item: "invalid_option", label: _t("Invalid Variant/Addons") },
    unspecified: { id: 11, item: "unspecified", label: _t("Others") },
};

patch(TicketScreen.prototype, {
    setup() {
        super.setup(...arguments);
        useEffect(() => {
            Object.assign(this.state, this.props.stateOverride || {});
            this.state.upState = this.props.upState;
        });
    },

    get presetFilterButtons() {
        return super.presetFilterButtons.filter((preset) => preset.identification !== "online");
    },

    _getSearchFields() {
        return Object.assign({}, super._getSearchFields(...arguments), {
            DELIVERYPROVIDER: {
                repr: (order) => order.getDeliveryProviderName(),
                displayName: _t("Delivery Channel"),
                modelField: "delivery_provider_id.name",
            },
            ORDERSTATUS: {
                repr: (order) => order.getOrderStatus(),
                displayName: _t("Delivery Order Status"),
                modelField: "delivery_status",
            },
            DELIVERYID: {
                repr: (order) => order.delivery_identifier,
                displayName: _t("Delivery ID"),
                modelField: "delivery_identifier",
            },
        });
    },

    async _handleResponse(response, order, new_status) {
        let { is_success, message } = response;
        if (!is_success) {
            if (new_status === "cancelled") {
                message = message.replace(" Callback requested instead.", "");
                message += _t(" Contact your provider for support.");
            }
            this.pos.notification.add(message, {
                type: "warning",
                sticky: false,
            });
            return false;
        }
        order.delivery_status = new_status;
        return true;
    },

    async _updateScreenState(filterState, upState = "") {
        this.state.upState = upState;
        await this.onFilterSelected(filterState);
    },

    async _updateOrderStatus(order, status, code = null, preparation_time = null) {
        const opt = {};
        if (status === "Cancelled") {
            opt.context = {
                cancellation_reason: CANCELLATION_REASONS[code]?.label || "",
                cancelled_by: order.getCashierName() || "",
            };
        }
        const response = await this.pos.data.call(
            "pos.order",
            "order_status_update",
            [
                order.id,
                status,
                code,
                {
                    orderPrepTime: order.prep_time,
                    preparation_time: preparation_time,
                },
            ],
            opt
        );
        return response;
    },

    async _acceptOrder(order) {
        const syncedOrder = this.pos.models["pos.order"].get(order.id);
        const response = await this._updateOrderStatus(syncedOrder, "Acknowledged");
        const status = await this._handleResponse(response, syncedOrder, "acknowledged");
        if (status) {
            await this.pos._sendDeliveryOrderForPreparation(syncedOrder);
            this._updateScreenState("ACTIVE_ORDERS");
            syncedOrder.uiState.orderAcceptTime = luxon.DateTime.now().ts;
        }
    },

    async _rejectOrder(order) {
        if (
            ["deliveroo", "", "hungerstation"].includes(order.delivery_provider_id.technical_name)
        ) {
            return this.dialog.add(AlertDialog, {
                title: _t("Oh snap !"),
                body: _t(`Rejecting this order is not allowed for "%(providerName)s"`, {
                    providerName: order.delivery_provider_id.name,
                }),
            });
        }
        this.dialog.add(SelectionPopup, {
            title: _t("Reject Order"),
            list: Object.values(CANCELLATION_REASONS),
            getPayload: async (code) => {
                const last_order_status = order.delivery_status;
                order.state = "cancel";
                const response = await this._updateOrderStatus(order, "Cancelled", code);
                const status = await this._handleResponse(response, order, "cancelled");
                if (status) {
                    const prepOrder = order.prep_order_ids || [];
                    if (prepOrder.length == 0 && last_order_status !== "placed") {
                        if (order.general_customer_note) {
                            order.last_general_customer_note = order.general_customer_note;
                        }
                        await this.pos.sendOrderInPreparationUpdateLastChange(order, {
                            cancelled: true,
                        });
                    }
                    await this._updateScreenState("ACTIVE_ORDERS");
                    await this.pos.deleteOrders([order]);
                    await this.pos.afterOrderDeletion();
                    this.setSelectedOrder(this.pos.getOrder());
                }
            },
        });
    },

    async _doneOrder(order) {
        const preparationTime =
            (luxon.DateTime.now().ts - order.uiState.orderAcceptTime) / (1000 * 60);
        const response = await this._updateOrderStatus(order, "Food Ready", false, preparationTime);
        const status = await this._handleResponse(response, order, "food_ready");
        if (status) {
            this._updateScreenState("SYNCED", "DONE");
        }
        await this.pos.data.loadServerOrders([["uuid", "=", order.uuid]]);

        // make sure the order is identified as paid.
        order = this.pos.models["pos.order"].get(order.id);
        this.state.selectedOrderUuid = order.uuid;
        order.setScreenData({ name: "" });
    },

    async _dispatchOrder(order) {
        const response = await this._updateOrderStatus(order, "Dispatched");
        await this._handleResponse(response, order, "dispatched");
    },

    async _completeOrder(order) {
        const response = await this._updateOrderStatus(order, "Completed");
        await this._handleResponse(response, order, "completed");
    },

    async _onInfoOrder(order) {
        if (order.delivery_identifier) {
            let previousOrderCount = 0;
            try {
                const partnerId = order.partner_id?.id;
                if (partnerId) {
                    previousOrderCount = await this.pos.data.orm.searchCount("pos.order", [
                        ["partner_id", "=", partnerId],
                        ["delivery_identifier", "!=", ""],
                        ["state", "=", "paid"],
                    ]);
                }
            } catch (error) {
                console.log(error);
            } finally {
                this.dialog.add(OrderInfoPopup, {
                    order,
                    previousOrderCount,
                });
            }
        } else {
            super._onInfoOrder(order);
        }
    },

    /**
     * @override
     * Return results based on upState.
     */
    getFilteredOrderList() {
        const orders = super.getFilteredOrderList();
        if (!this.state.upState) {
            return orders;
        }

        const statusMapping = {
            NEW: "placed",
            ONGOING: "acknowledged",
            DONE: ["food_ready", "dispatched", "completed"],
        };

        const filteredOrders = orders.filter((order) => {
            if (this.state.upState === "DONE") {
                return statusMapping.DONE.includes(order.delivery_status);
            }
            return order.delivery_status === statusMapping[this.state.upState];
        });

        return filteredOrders;
    },

    /**
     * @override
     */
    getDate(order) {
        if (order?.delivery_identifier) {
            if (
                order.date_order.toLocal().startOf("day").ts ===
                luxon.DateTime.now().startOf("day").ts
            ) {
                return _t("Today");
            }
            return order.date_order.toFormat("MM/dd/yyyy");
        }
        return super.getDate(order);
    },

    /**
     * @override
     */
    async onFilterSelected(selectedFilter) {
        if (this.state.upState && this.state.filter != selectedFilter) {
            this.state.upState = "";
        }
        super.onFilterSelected(selectedFilter);
    },

    /**
     * @override
     */
    async onSearch(search) {
        if (this.state.upState && this.state.search != search) {
            this.state.upState = "";
        }
        super.onSearch(search);
    },

    shouldShowPlatformFilterButton() {
        return this.pos.config.module_pos_urban_piper
            ? true
            : super.shouldShowPlatformFilterButton();
    },

    getMaxTimePreset(order) {
        if (order.isDeliveryOrder) {
            return order.prep_time;
        }
        return super.getMaxTimePreset(order);
    },
});
