import { test, expect } from "@odoo/hoot";
import { getFilledOrder, setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

test("isCustomerRequired", async () => {
    const posStore = await setupPosEnv();
    const order = await getFilledOrder(posStore);
    // partner is required for EC company
    expect(order.isCustomerRequired).toBe(true);
    const existingPartner = posStore.models["res.partner"].get(3);
    order.partner_id = existingPartner;
    expect(order.isCustomerRequired).toBe(false);
});

test("unchecked to_invoice survives a sync", async () => {
    const posStore = await setupPosEnv();
    const order = await getFilledOrder(posStore);
    order.setPartner(posStore.models["res.partner"].get(3));
    order.setToInvoice(false);
    await posStore.syncAllOrders({ orders: [order] });
    expect(order.to_invoice).toBe(false);
});

test("new order is invoiced by default", async () => {
    const posStore = await setupPosEnv();
    const newOrder = posStore.addNewOrder();
    expect(newOrder.to_invoice).toBe(true);
});
