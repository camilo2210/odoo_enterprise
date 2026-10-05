import { test, expect, describe, beforeEach } from "@odoo/hoot";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { getFilledOrder } from "@point_of_sale/../tests/unit/utils";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";

definePosModels();

describe("pos_platform_order: PosStore deleteOrders", () => {
    let ordersInPreparation = [];

    beforeEach(() => {
        ordersInPreparation = [];
    });

    test("Skips sending to preparation when deleting non-accepted platform orders", async () => {
        const store = await setupPosEnvForPrepDisplay();
        const order1 = await getFilledOrder(store, { table_id: 1 });
        const order2 = await getFilledOrder(store, { table_id: 2 });
        const provider = store.models["platform.order.provider"].get(1);
        order1.platform_order_provider_id = provider;
        order1.platform_order_status = "new";
        order2.platform_order_provider_id = provider;
        order2.platform_order_status = "accepted";

        expect(store.models["pos.order"].get(order1.id).platform_order_status).toBe("new");
        expect(store.models["pos.order"].get(order2.id).platform_order_status).toBe("accepted");
        await store.syncAllOrders();
        order2.updateLastOrderChange();

        store.sendOrderInPreparation = async (order, opts = {}) => {
            ordersInPreparation.push(order);
            return true;
        };

        await store.deleteOrders([order1]);
        expect(ordersInPreparation).toHaveLength(0);

        await store.deleteOrders([order2]);
        expect(ordersInPreparation).toHaveLength(1);
    });

    test("Skips sending to preparation when deleting a cancelled platform order with ignoreChange set to true", async () => {
        const store = await setupPosEnvForPrepDisplay();
        const order = await getFilledOrder(store, { table_id: 1 });
        const provider = store.models["platform.order.provider"].get(1);

        order.platform_order_provider_id = provider;
        order.platform_order_status = "cancelled";

        await store.syncAllOrders();

        store.sendOrderInPreparation = async (order, opts = {}) => {
            ordersInPreparation.push(order);
            return true;
        };

        await store.deleteOrders([order], [], true);

        expect(ordersInPreparation).toHaveLength(0);
    });

    test("_fetchPlatformOrder passes ignoreChange=true when a 'new' order becomes 'cancelled'", async () => {
        const store = await setupPosEnvForPrepDisplay();
        const order = await getFilledOrder(store, { table_id: 1 });
        const provider = store.models["platform.order.provider"].get(1);

        order.platform_order_provider_id = provider;
        order.platform_order_status = "new";
        await store.syncAllOrders();

        store.getServerOrder = async (order_id) => {
            const localOrder = store.models["pos.order"].get(order_id);
            if (localOrder) {
                localOrder.platform_order_status = "cancelled";
            }
        };

        store.data.callRelated = async (model, method, args) => {
            if (model === "pos.order" && method === "mark_platform_prep_order_as_printed") {
                return true;
            }
            return false;
        };

        let deleteOrdersArgs = null;
        store.deleteOrders = async (orders, serverIds, ignoreChange) => {
            deleteOrdersArgs = { orders, serverIds, ignoreChange };
            return [];
        };

        await store._fetchPlatformOrder(order.id, false);

        expect(deleteOrdersArgs).not.toBe(null);
        expect(deleteOrdersArgs.orders[0].id).toBe(order.id);
        expect(deleteOrdersArgs.ignoreChange).toBe(true);
    });

    test("_fetchPlatformOrder handles full lifecycle: new -> accepted -> cancelled", async () => {
        const store = await setupPosEnvForPrepDisplay();
        const order = await getFilledOrder(store, { table_id: 1 });
        const provider = store.models["platform.order.provider"].get(1);

        order.platform_order_provider_id = provider;
        order.platform_order_status = "new";
        await store.syncAllOrders();

        let nextServerStatus = "new";
        store.getServerOrder = async (order_id) => {
            const localOrder = store.models["pos.order"].get(order_id);
            if (localOrder) {
                localOrder.platform_order_status = nextServerStatus;
            }
        };

        store.data.callRelated = async (model, method, args) => {
            if (model === "pos.order" && method === "mark_platform_prep_order_as_printed") {
                return true;
            }
            return false;
        };

        let notificationDisplayed = false;
        store._displayNewPlatformOrderNotification = () => {
            notificationDisplayed = true;
        };

        let sentToPreparation = false;
        store.sendOrderInPreparationUpdateLastChange = async () => {
            sentToPreparation = true;
        };

        let deleteOrdersArgs = null;
        store.deleteOrders = async (orders, serverIds, ignoreChange) => {
            deleteOrdersArgs = { orders, serverIds, ignoreChange };
            return [];
        };

        nextServerStatus = "new";
        await store._fetchPlatformOrder(order.id, true);
        expect(notificationDisplayed).toBe(true);

        nextServerStatus = "accepted";
        await store._fetchPlatformOrder(order.id, false);
        expect(sentToPreparation).toBe(true);

        nextServerStatus = "cancelled";
        await store._fetchPlatformOrder(order.id, false);

        expect(deleteOrdersArgs).not.toBe(null);
        expect(deleteOrdersArgs.orders[0].id).toBe(order.id);
        expect(deleteOrdersArgs.ignoreChange).toBe(false);
    });
});
