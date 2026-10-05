import { test, expect } from "@odoo/hoot";
import { getFilledOrder, setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import "@l10n_de_pos_cert/app/models/pos_order";
import "@l10n_de_pos_cert/app/services/pos_store";
import "@l10n_de_pos_res_cert/app/services/pos";

definePosModels();

test("second split context: pending orders are synced in DE Fiskaly restaurant flow", async () => {
    const store = await setupPosEnv();
    store.config.module_pos_restaurant = true;
    store.config.is_company_country_germany = true;
    store.config.l10n_de_fiskaly_tss_id = "tss-id|client-id";

    let orderTxCalls = 0;
    store.createOrderTransaction = async (order) => {
        orderTxCalls += 1;
        order.transactionStarted();
    };

    const parentOrder = await getFilledOrder(store);
    const line = parentOrder.getOrderlines()[0];

    let syncCalls = 0;
    const originalCall = store.data.call.bind(store.data);
    store.data.call = async (model, method, args, kwargs) => {
        if (model === "pos.order" && method === "sync_from_ui") {
            syncCalls += 1;
        }
        return originalCall(model, method, args, kwargs);
    };

    // First split: parent qty reduced, sync via pending queue.
    line.setQuantity(2);
    store.clearPendingOrder();
    store.addPendingOrder([parentOrder.id]);
    await store.syncAllOrders();
    expect(orderTxCalls).toBe(1);
    expect(syncCalls).toBe(1);

    // Second split: order transaction already started, only Odoo sync is needed.
    line.setQuantity(1);
    store.clearPendingOrder();
    store.addPendingOrder([parentOrder.id]);
    await store.syncAllOrders();
    expect(orderTxCalls).toBe(1);
    expect(syncCalls).toBe(2);
});
