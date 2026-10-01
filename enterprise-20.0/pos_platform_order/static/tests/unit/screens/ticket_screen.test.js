import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { test, expect } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { getFilledOrder, makeOrder } from "@point_of_sale/../tests/unit/utils";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";
import { getPlatformFilledOrder } from "../utils";

definePosModels();

test("shouldShowPlatformFilterButton", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(TicketScreen, {});

    store.config._has_platform_order_entity = false;
    expect(comp.shouldShowPlatformFilterButton()).toBe(false);

    store.config._has_platform_order_entity = true;
    expect(comp.shouldShowPlatformFilterButton()).toBe(true);
});

test("togglePlatformFilter", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(TicketScreen, {});

    const order1 = await getPlatformFilledOrder(store);
    const order2 = await getFilledOrder(store);
    const preset = store.models["pos.preset"].get(1);

    expect(comp.state.isPlatformFilterActive).toBe(false);
    expect(comp.state.selectedPreset).toBe(null);

    comp.togglePlatformFilter();
    expect(comp.state.isPlatformFilterActive).toBe(true);
    expect(comp.state.selectedPreset).toBe(null);
    expect(comp.state.selectedOrderUuid).toBe(order1.uuid);

    comp.onPresetSelected(preset);
    expect(comp.state.isPlatformFilterActive).toBe(false);
    expect(comp.state.selectedPreset.id).toBe(preset.id);
    expect(comp.state.selectedOrderUuid).toBe(order2.uuid);
});

test("getFilteredOrderList", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const screen = await mountWithCleanup(TicketScreen);
    const provider = store.models["platform.order.provider"].get(1);

    makeOrder(store, {
        pos_reference: "O-01",
        state: "paid",
        platform_order_provider_id: provider,
        platform_order_status: "delivered",
    });
    makeOrder(store, {
        pos_reference: "O-02",
        state: "paid",
        platform_order_provider_id: provider,
        platform_order_status: "collected",
    });
    makeOrder(store, {
        pos_reference: "O-03",
        state: "draft",
        platform_order_provider_id: provider,
        platform_order_status: "cancelled",
    });
    makeOrder(store, { pos_reference: "O-04", state: "paid" });
    makeOrder(store, { pos_reference: "O-05", state: "cancel" });

    screen.state.filter = "SYNCED";
    const result = screen.getFilteredOrderList();
    expect(result.length).toBe(2);
    expect(result[0].pos_reference).toBe("O-04");
    expect(result[1].pos_reference).toBe("O-01");

    screen.state.filter = "CANCELLED";
    const cancelledResult = screen.getFilteredOrderList();
    expect(cancelledResult.length).toBe(2);
    expect(cancelledResult[0].pos_reference).toBe("O-05");
    expect(cancelledResult[1].pos_reference).toBe("O-03");

    screen.state.filter = "ACTIVE_ORDERS";
    const activeResult = screen.getFilteredOrderList();
    expect(activeResult.length).toBe(1);
    expect(activeResult[0].pos_reference).toBe("O-02");
});

test("isOrderDoneOrPaid", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const screen = await mountWithCleanup(TicketScreen);
    const provider = store.models["platform.order.provider"].get(1);
    const order = store.addNewOrder();

    order.platform_order_provider_id = provider;

    order.platform_order_status = "delivered";
    expect(screen.isOrderDoneOrPaid(order)).toBe(true);

    order.platform_order_status = "collected";
    expect(screen.isOrderDoneOrPaid(order)).toBe(false);

    order.platform_order_status = "new";
    expect(screen.isOrderDoneOrPaid(order)).toBe(false);

    order.platform_order_status = "cancelled";
    expect(screen.isOrderDoneOrPaid(order)).toBe(false);

    order.platform_order_provider_id = false;
    order.state = "paid";
    expect(screen.isOrderDoneOrPaid(order)).toBe(true);

    order.state = "cancel";
    expect(screen.isOrderDoneOrPaid(order)).toBe(false);
});

test("isOrderCancelled", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const screen = await mountWithCleanup(TicketScreen);
    const provider = store.models["platform.order.provider"].get(1);
    const order = store.addNewOrder();

    order.platform_order_provider_id = provider;

    order.platform_order_status = "cancelled";
    expect(screen.isOrderCancelled(order)).toBe(true);

    order.platform_order_status = "failed";
    expect(screen.isOrderCancelled(order)).toBe(true);

    order.platform_order_status = "delivered";
    expect(screen.isOrderCancelled(order)).toBe(false);

    order.platform_order_status = "new";
    expect(screen.isOrderCancelled(order)).toBe(false);

    order.platform_order_provider_id = false;
    order.state = "cancel";
    expect(screen.isOrderCancelled(order)).toBe(true);

    order.state = "paid";
    expect(screen.isOrderCancelled(order)).toBe(false);
});

test("getStatusDecoration", async () => {
    await setupPosEnvForPrepDisplay();
    const screen = await mountWithCleanup(TicketScreen);

    expect(screen.getStatusDecoration("New")).toBe("info");
    expect(screen.getStatusDecoration("Failed")).toBe("danger");

    expect(screen.getStatusDecoration("Ongoing")).toBe("info");
    expect(screen.getStatusDecoration("Payment")).toBe("info");
    expect(screen.getStatusDecoration("Receipt")).toBe("success");
    expect(screen.getStatusDecoration("Paid")).toBe("success");
    expect(screen.getStatusDecoration("Cancelled")).toBe("danger");
    expect(screen.getStatusDecoration("anything")).toBe("secondary");
});

test("getStatus", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const screen = await mountWithCleanup(TicketScreen);
    const platformProvider = store.models["platform.order.provider"].get(1);

    const order = store.addNewOrder();
    order.platform_order_provider_id = platformProvider;

    order.platform_order_status = "cancelled";
    expect(screen.getStatus(order)).toBe("Cancelled");
    order.platform_order_status = "new";
    expect(screen.getStatus(order)).toBe("New");
    order.platform_order_status = "accepted";
    expect(screen.getStatus(order)).toBe("Ongoing");
    order.platform_order_status = "collected";
    expect(screen.getStatus(order)).toBe("Paid");
    order.platform_order_status = "delivered";
    expect(screen.getStatus(order)).toBe("Paid");
    order.platform_order_status = "failed";
    expect(screen.getStatus(order)).toBe("Failed");
    order.platform_order_status = "unknown";
    expect(screen.getStatus(order)).toBeEmpty();
});
