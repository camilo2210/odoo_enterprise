import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { uuidv4 } from "@point_of_sale/utils";

patch(PosStore.prototype, {
    isRestaurantCountryGermanyAndFiskaly() {
        return this.isCountryGermanyAndFiskaly() && this.config.module_pos_restaurant;
    },

    // Fiskaly Order API calls payload helpers
    getOrderUpdates(orderChanges, tx_revision) {
        const data = { order: { line_items: [] } };
        const changedLines = [...orderChanges.addedQuantity, ...orderChanges.removedQuantity];
        // If `tx_revision` is `1`, send empty data on the first activation call, as it is only used for activation.
        // line details will be sent from next syncronization
        if (!orderChanges || !changedLines.length || tx_revision == 1) {
            return data;
        }

        changedLines.forEach((line) => {
            const qty = line.quantity || line.qty;
            const sign = qty < 0 ? -1 : 1;
            data.order.line_items.push({
                // Finished orders use `qty` and `full_product_name`, while active orders use regular order changes.
                quantity: String(qty),
                text: line.basic_name || line.full_product_name,
                price_per_unit: (line.price_unit * sign).toFixed(2),
            });
        });
        return data;
    },
    /**
     * Compute and return only the changes made to the order since the last synchronization.
     *
     * For example:
     * - If a product quantity changes from 5 to 8, only the additional quantity (3) is sent.
     * - If a product quantity changes from 5 to 3, only the removed quantity (-2) is sent.
     *
     * The computation is based on all available order changes (iface_available_categ_ids) using the `changesToOrder`
     * method, and not on preparation categories, since all updates must be synchronized.
     */
    orderUpdatePayload(order, state) {
        let linesData;
        if (order && ["FINISHED", "CANCELLED"].includes(state)) {
            // send entire cart at the end
            linesData = this.getOrderUpdates({ addedQuantity: order.lines, removedQuantity: [] });
        } else {
            // Only updates should be sent like 2 qty added for product A and 2 removed for product B.
            const orderChanges = order.getChanges();
            // For cancelled lines when changesToOrder return 1, means 1 cancelled so the line have -1 qty.
            orderChanges.removedQuantity.forEach((l) => (l.quantity *= -1));
            linesData = this.getOrderUpdates(orderChanges, order.uiState.tx_revision);
        }
        return {
            state: state,
            client_id: this.getClientId(),
            schema: {
                standard_v1: linesData,
            },
            metadata: {
                pos_config_id: order.config_id.id,
                pos_order_uuid: order.uuid,
            },
        };
    },

    // Fiskaly Order API calls
    async createOrderTransaction(order) {
        const transactionUuid = order.uiState.l10n_de_fiskaly_order_tx_uuid || uuidv4();
        const data = this.orderUpdatePayload(order, "ACTIVE");
        const payload = `${transactionUuid}${
            this.isUsingApiV2() ? `?tx_revision=${order.uiState.tx_revision}` : ""
        }`;
        const result = await this.transactionCall(payload, data, order);
        if (result) {
            order.uiState.l10n_de_fiskaly_order_tx_uuid = transactionUuid;
            order.transactionStarted();
        }
    },
    async finishOrderTransaction(order) {
        const data = this.orderUpdatePayload(order, "FINISHED");
        const payload = `${order.uiState.l10n_de_fiskaly_order_tx_uuid}?${
            this.isUsingApiV2() ? `tx_revision=${order.uiState.tx_revision}` : "last_revision=1"
        }`;
        const result = await this.transactionCall(payload, data, order);
        if (!order.fiskalyServerError && result) {
            order._updateTssInfo(result);
        }
    },
    async cancelOrderTransaction(order) {
        const data = this.orderUpdatePayload(order, "CANCELLED");
        const payload = `${order.uiState.l10n_de_fiskaly_order_tx_uuid}?${
            this.isUsingApiV2() ? `tx_revision=${order.uiState.tx_revision}` : "last_revision=1"
        }`;
        await this.transactionCall(payload, data, order);
        order.uiState.transactionState = "inactive";
        order.uiState.l10n_de_fiskaly_order_tx_uuid = "";
        order.uiState.tx_revision = 1;
    },

    /**
     * @override
     */
    // Initialize order transaction on first line add
    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        // we need to start order transaction only for restaurants
        if (!this.isRestaurantCountryGermanyAndFiskaly()) {
            return await super.addLineToCurrentOrder(vals, opts, configure);
        }
        // If same product added multiple times it will be better to check before adding line if there was an empty order or not
        const order = this.getOrder();
        const isEmptyOrder = order.isEmpty();
        const newLine = await super.addLineToCurrentOrder(vals, opts, configure);
        // This call initiates the transaction when the first item is added to the cart.
        if (isEmptyOrder && order.isTransactionInactive()) {
            try {
                await this.createOrderTransaction(order);
            } catch (error) {
                this.fiskalyError(error);
                return false;
            }
        }
        return newLine;
    },
    // update order transaction on each time we send it to kitchen
    async sendOrderInPreparation(o, cancelled = false) {
        if (!o.isTransactionFinished() && this.isRestaurantCountryGermanyAndFiskaly()) {
            await this.createOrderTransaction(o);
        }
        return await super.sendOrderInPreparation(o, cancelled);
    },
    // cancel order transaction
    async handleFiskalyCancellation(order) {
        try {
            this.env.services.ui.block();
            if (this.isRestaurantCountryGermanyAndFiskaly()) {
                if (order.uiState.l10n_de_fiskaly_order_tx_uuid && order.isTransactionInactive()) {
                    await this.fetchTransaction(order);
                }
                if (order?.uiState?.l10n_de_fiskaly_order_tx_uuid) {
                    await this.cancelOrderTransaction(order);
                }
            }
        } catch (error) {
            this.fiskalyError(error);
            return false;
        } finally {
            this.env.services.ui.unblock();
        }
        return super.handleFiskalyCancellation(order);
    },
    // fetch transaction from fiskaly in case of multi device to get updated tx_revision
    async fetchTransaction(order) {
        const txId = order.uiState.l10n_de_fiskaly_order_tx_uuid;
        if (!txId) {
            return;
        }
        let token = this.getApiToken();
        if (!token) {
            await this._authenticate();
            token = this.getApiToken();
        }
        const response = await fetch(`${this.getApiUrl()}/tss/${this.getTssId()}/tx/${txId}`, {
            headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
            },
            method: "GET",
        });
        if (response.ok) {
            const result = await response.json();
            // Sync the revision so subsequent PUT calls use the correct value.
            order.uiState.tx_revision = result.revision + 1;
            if (result.state === "ACTIVE") {
                order.transactionStarted();
            }
        }
    },
    // update transaction payload to have link with order transaction
    getTransactionPayload(order, state, receiptType = "RECEIPT") {
        const payload = super.getTransactionPayload(order, state, (receiptType = "RECEIPT"));
        payload.metadata["fiskaly_order_tx_uuid"] = order.uiState.l10n_de_fiskaly_order_tx_uuid;
        return payload;
    },
    //@Override
    /**
     * This function first attempts to send the orders remaining in the queue to Fiskaly before trying to
     * send it to Odoo. Two cases can happen:
     * - Failure to send to Fiskaly => we assume that if one order fails, EVERY order will fail
     * - Failure to send to Odoo => the order is already sent to Fiskaly, we store them locally with the TSS info
     */
    async handleOrderTransaction(order, orderObject) {
        // order transaction is only needed for restaurants
        if (this.isRestaurantCountryGermanyAndFiskaly()) {
            if (orderObject.isTransactionInactive()) {
                await this.createOrderTransaction(order);
            }
            if (orderObject.isTransactionStarted() && order.state == "paid") {
                // finish the transaction based on the state of order if paid than finish else update it
                await this.finishOrderTransaction(order);
                return super.handleOrderTransaction(order, orderObject);
            }
        }
        return super.handleOrderTransaction(order, orderObject);
    },
    shouldSyncOrder(orderObject) {
        const isReceiptTxnSent = super.shouldSyncOrder(orderObject);
        if (this.isRestaurantCountryGermanyAndFiskaly()) {
            const isOrderTxnSent =
                !orderObject.isTransactionInactive() ||
                orderObject.fiskalyServerError ||
                orderObject.networkError;
            if (orderObject.state !== "paid") {
                // Receipt txn will be sent when payment starts
                return isOrderTxnSent;
            } else {
                // At the time of payment both order and receipt both txn should be registered
                return isReceiptTxnSent && isOrderTxnSent;
            }
        }
        return isReceiptTxnSent;
    },
});
