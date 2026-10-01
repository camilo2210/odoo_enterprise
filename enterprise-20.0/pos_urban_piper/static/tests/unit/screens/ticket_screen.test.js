import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { test, expect, waitFor, animationFrame } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { getFilledOrder } from "@point_of_sale/../tests/unit/utils";
import { getUrbanPiperFilledOrder } from "@pos_urban_piper/../tests/unit/utils";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";

definePosModels();

test("togglePlatformFilter", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(TicketScreen, {});

    const order1 = await getUrbanPiperFilledOrder(store);
    order1.delivery_status = "food_ready";
    await waitFor(".info-column");
    expect(".info-column").toHaveCount(1);
    const order2 = await getFilledOrder(store);
    const preset = store.models["pos.preset"].get(1);

    comp.togglePlatformFilter();
    expect(comp.state.isPlatformFilterActive).toBe(true);
    comp.togglePlatformFilter();

    await animationFrame();
    expect(".info-column").toHaveCount(2);

    expect(comp.state.selectedPreset).toBe(null);
    expect(comp.state.selectedOrderUuid).toBe(order1.uuid);

    comp.onPresetSelected(preset);
    await animationFrame();
    expect(".info-column").toHaveCount(1);
    expect(comp.state.isPlatformFilterActive).toBe(false);
    expect(comp.state.selectedPreset.id).toBe(preset.id);
    expect(comp.state.selectedOrderUuid).toBe(order2.uuid);
});

test("onPresetSelected", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(TicketScreen, {});

    const preset = store.models["pos.preset"].get(1);
    const order1 = await getUrbanPiperFilledOrder(store); //UrbanPiper Order
    order1.delivery_status = "food_ready";
    const order_2 = await getFilledOrder(store); //Normal Order

    expect(comp.state.isPlatformFilterActive).toBe(false);
    expect(comp.state.selectedPreset).toBe(null);

    comp.onPresetSelected(preset);
    expect(comp.state.isPlatformFilterActive).toBe(false);
    expect(comp.state.selectedPreset.id).toBe(preset.id);
    expect(comp.state.selectedOrderUuid).toBe(order_2.uuid);
});

test("_getSearchFields", async () => {
    await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(TicketScreen, {});
    const fields = comp._getSearchFields();
    expect(Object.keys(fields)).toEqual([
        "REFERENCE",
        "RECEIPT_NUMBER",
        "INVOICE_NUMBER",
        "DATE",
        "PARTNER",
        "DELIVERYPROVIDER",
        "ORDERSTATUS",
        "DELIVERYID",
    ]);
});

test("_acceptOrder, _dispatchOrder, _completeOrder", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    const comp = await mountWithCleanup(TicketScreen, {});

    await comp._acceptOrder(order);
    expect(comp.state.upState).toBeEmpty();
    expect(order.delivery_status).toBe("acknowledged");
    expect(order.uiState.orderAcceptTime).not.toBeEmpty();

    await comp._dispatchOrder(order);
    expect(order.delivery_status).toBe("dispatched");
    expect(comp.state.upState).toBeEmpty();

    await comp._completeOrder(order);
    expect(order.delivery_status).toBe("completed");
    expect(comp.state.upState).toBeEmpty();
});

test("getFilteredOrderList", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(TicketScreen, {});
    (await getUrbanPiperFilledOrder(store)).delivery_status = "food_ready";
    (await getUrbanPiperFilledOrder(store)).delivery_status = "dispatched";
    (await getUrbanPiperFilledOrder(store)).delivery_status = "completed";
    (await getUrbanPiperFilledOrder(store)).delivery_status = "placed";
    comp.state.upState = "DONE";
    expect((await comp.getFilteredOrderList()).map((o) => o.delivery_status)).toEqual([
        "food_ready",
        "dispatched",
        "completed",
    ]);
});

test("getDate", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    const comp = await mountWithCleanup(TicketScreen, {});
    expect(comp.getDate(order)).toBe("Today");
    order.date_order = luxon.DateTime.now().minus({ days: 1 });
    expect(comp.getDate(order)).toMatch(/\d{2}\/\d{2}\/\d{4}/);
});

test("shouldShowPlatformFilterButton", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(TicketScreen, {});

    store.config.module_pos_urban_piper = false;
    expect(comp.shouldShowPlatformFilterButton()).toBe(false);

    store.config.module_pos_urban_piper = true;
    expect(comp.shouldShowPlatformFilterButton()).toBe(true);
});
