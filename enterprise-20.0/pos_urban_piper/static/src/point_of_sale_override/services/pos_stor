import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { Domain } from "@web/core/domain";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";
import { base64ToBlob, UP_CONSOLE_COLOR } from "@pos_urban_piper/utils";

patch(PosStore.prototype, {
    /**
     * @override
     */
    async setup() {
        await super.setup(...arguments);
        if (!this.config.urbanpiper_store_id) {
            return;
        }
        this.delivery_order_count = {};
        this._initStoreOrderReceiveTone();
        await this._fetchUrbanpiperOrder(false);

        this.data.connectWebSocket(
            "PRODUCT_UP_STATUS_CHANGED",
            this._notifyFoodDeliveryStatus.bind(this)
        );
        this.data.connectWebSocket(
            "URBANPIPER_DELIVERY_ORDER",
            this._fetchUrbanpiperOrder.bind(this)
        );
        this.data.connectWebSocket("STORE_ACTION", this._fetchStoreAction.bind(this));
        this.data.connectWebSocket(
            "FUTURE_ORDER_NOTIFICATION",
            this._handleFutureOrders.bind(this)
        );
    },

    _notifyFoodDeliveryStatus(data) {
        const { product_ids, status } = data;
        const products = this.models["product.template"].filter((product) =>
            product_ids.includes(product.id)
        );
        if (!products.length || !this.config.urbanpiper_store_id) {
            return;
        }
        products.forEach((product) => {
            product.setFoodDeliveryAvailability(status, this.config.urbanpiper_store_id.id);
            this.notification.add(
                _t(
                    "%s is %s online food delivery for all platform in this locations.",
                    product.name,
                    status ? _t("enabled") : _t("disabled")
                ),
                {
                    type: status ? "success" : "warning",
                    sticky: false,
                }
            );
        });
    },

    getServerOrdersDomain() {
        const base = super.getServerOrdersDomain();
        if (this.config.module_pos_urban_piper && this.config.urbanpiper_store_id) {
            return Domain.or([
                base,
                new Domain([
                    ["state", "=", "draft"],
                    ["session_id", "=", this.session.id],
                    [
                        "delivery_provider_id",
                        "in",
                        this.config.urbanpiper_store_id.delivery_provider_ids.map(
                            (provider) => provider.id
                        ),
                    ],
                ]),
            ]);
        }
        return base;
    },

    _fetchStoreAction(data) {
        const params = {
            type: "success",
            sticky: false,
        };
        let message = "";
        // Prepare notification message
        const store = this.config.urbanpiper_store_id;
        if (!data.status) {
            params.type = "danger";
            message = _t("Error occurred while updating " + data.platform + " status.");
        } else if (data.action === "enable") {
            message = _t(store.name + " is online on " + data.platform + ".");
        } else if (data.action === "disable") {
            message = _t(store.name + " is offline on " + data.platform + ".");
        }

        if (message) {
            this.notification.add(message, params);
        }
    },

    async _handleFutureOrders(orderIds) {
        this.sound.play("notification");
        this.notification.add(_t("Scheduled Delivery Order"), {
            type: "info",
            sticky: true,
        });
        const futureOrders = this.models["pos.order"].filter((o) => orderIds.includes(o.id));
        for (const order of futureOrders) {
            try {
                await this._sendDeliveryOrderForPreparation(order);
            } catch {
                this.notification.add(_t("Error to send delivery order in preparation display."), {
                    type: "warning",
                    sticky: false,
                });
            }
        }
    },

    _initStoreOrderReceiveTone() {
        this.storeOrderTone = "order-receive-tone"; // Default order notification sound
        this.isSoundPlaying = false;

        const soundData = this.config.urbanpiper_store_id.order_notification_sound;
        if (!soundData) {
            return;
        }
        try {
            const blob = base64ToBlob(soundData, "audio/mpeg");
            const storeAudioPath = URL.createObjectURL(blob);
            const storeAudio = new Audio(storeAudioPath);
            this.sound.soundEffects["store-custom-order-receive-tone"] = {
                path: storeAudioPath,
                audio: storeAudio,
            };
            this.storeOrderTone = "store-custom-order-receive-tone";
        } catch (error) {
            logPosMessage(
                "UrbanPiper Store",
                "orderNotificationSound",
                "Failed to get urbanpiper Order notification sound",
                UP_CONSOLE_COLOR,
                [error]
            );
        }
    },

    get notificationOptions() {
        const reviewOrder = () => {
            this.closeNotificationFn?.();
            const stateOverride = {
                search: {
                    fieldName: "DELIVERYPROVIDER",
                    searchTerm: this.deliveryOrderNotification?.delivery_provider_id.name,
                },
                filter: "ACTIVE_ORDERS",
            };
            this.setOrder(this.deliveryOrderNotification);
            if (this.router.currentScreen() == "TicketScreen") {
                const next = this.defaultPage;
                this.navigate(next.page, next.params);
                setTimeout(() => {
                    this.navigate("TicketScreen", { stateOverride });
                    this.ui.unblock();
                }, 300);
                return;
            }
            return this.navigate("TicketScreen", { stateOverride });
        };
        return {
            type: "success",
            sticky: true,
            buttons: [
                {
                    name: _t("Review Orders"),
                    onClick: reviewOrder,
                },
            ],
            onClose: () => {
                if (this.isSoundPlaying) {
                    this.sound.stop(this.storeOrderTone);
                    this.isSoundPlaying = false;
                }
            },
        };
    },

    async _fetchUrbanpiperOrder(order_id) {
        try {
            await this.getServerOrders();
        } catch {
            this.notification.add(_t("Order does not load from server"), {
                type: "warning",
                sticky: false,
            });
        }
        const response = await this.data.call(
            "pos.config",
            "get_urbanpiper_order_data",
            [this.config.id],
            {}
        );
        this.delivery_order_count = response.delivery_order_count;
        this.total_new_order = response.total_new_order;
        const deliveryOrder = order_id ? this.models["pos.order"].get(order_id) : false;
        if (!deliveryOrder) {
            return;
        }
        if (deliveryOrder.delivery_status === "acknowledged" && deliveryOrder.state != "cancel") {
            deliveryOrder.uiState.last_general_customer_note = "";
            deliveryOrder.uiState.last_internal_note = "";
            await this._sendDeliveryOrderForPreparation(deliveryOrder);
        } else if (deliveryOrder.delivery_status === "placed") {
            if (!this.isSoundPlaying) {
                this.isSoundPlaying = true;
                this.sound.play(this.storeOrderTone, { loop: true, volume: 1 });
                this.deliveryOrderNotification = deliveryOrder;
                this.closeNotificationFn = this.notification.add(
                    _t("New online order received."),
                    this.notificationOptions
                );
            }
        }
    },

    async _sendDeliveryOrderForPreparation(deliveryOrder) {
        if (deliveryOrder.urbanpiper_printed || deliveryOrder.isFutureOrder) {
            return;
        }
        let isReadyToPrint = true;
        try {
            isReadyToPrint = await this.data.call(
                "pos.order",
                "mark_urbanpiper_prep_order_as_printed",
                [deliveryOrder.id]
            );
        } catch {
            isReadyToPrint = false;
        }
        if (isReadyToPrint) {
            await this.sendOrderInPreparationUpdateLastChange(deliveryOrder);
        }
    },

    async goToBack() {
        this.addPendingOrder([this.getOrder().id]);
        await this.syncAllOrders();
        this.navigate("TicketScreen");
        if (this.getOrder().delivery_status !== "placed") {
            try {
                await this.sendOrderInPreparationUpdateLastChange(this.getOrder());
            } catch {
                this.notification.add(_t("Error to send in preparation display."), {
                    type: "warning",
                    sticky: false,
                });
            }
        }
    },

    async onDeleteOrder(order) {
        if (!order?.delivery_identifier) {
            return super.onDeleteOrder(...arguments);
        }
        this.dialog.add(AlertDialog, {
            title: _t("Online Order"),
            body: _t(
                "Online orders cannot be deleted. If needed, reject the order instead or contact the food delivery provider."
            ),
        });
        return false;
    },
    canEditPayment(order) {
        return order.delivery_identifier ? false : super.canEditPayment(order);
    },
});
