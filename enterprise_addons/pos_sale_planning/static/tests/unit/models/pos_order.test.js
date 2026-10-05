import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { test, expect } from "@odoo/hoot";
import { setupPosEnv, createPaymentLine } from "@point_of_sale/../tests/unit/utils";

const { DateTime } = luxon;

definePosModels();

test("hasResourcePayment - false when no payments", async () => {
    const store = await setupPosEnv();
    const order = store.addNewOrder();
    expect(order.hasResourcePayment).toBe(false);
});

test("hasResourcePayment - false when only non-resource payments", async () => {
    const store = await setupPosEnv();
    const order = store.addNewOrder();
    const cashPm = store.models["pos.payment.method"].get(1);
    createPaymentLine(store, order, cashPm);

    expect(order.hasResourcePayment).toBe(false);
});

test("hasResourcePayment - true when a resource payment exists", async () => {
    const store = await setupPosEnv();
    const order = store.addNewOrder();
    const resourcePm = store.models["pos.payment.method"].get(4);
    createPaymentLine(store, order, resourcePm);

    expect(order.hasResourcePayment).toBe(true);
});

test("setToInvoice - setting to true is blocked when order has a resource payment", async () => {
    const store = await setupPosEnv();
    const order = store.addNewOrder();
    const resourcePm = store.models["pos.payment.method"].get(4);
    createPaymentLine(store, order, resourcePm);

    order.setToInvoice(true);
    expect(order.to_invoice).toBe(false);
});

test("setToInvoice - setting to false is allowed even with a resource payment", async () => {
    const store = await setupPosEnv();
    const order = store.addNewOrder();
    const resourcePm = store.models["pos.payment.method"].get(4);
    createPaymentLine(store, order, resourcePm);
    order.to_invoice = true;

    order.setToInvoice(false);
    expect(order.to_invoice).toBe(false);
});

test("setToInvoice - setting to true is allowed when no resource payment", async () => {
    const store = await setupPosEnv();
    const order = store.addNewOrder();

    order.setToInvoice(true);
    expect(order.to_invoice).toBe(true);
});

test("addPaymentline - blocked when lines come from a sale order and payment method is resource type", async () => {
    const store = await setupPosEnv();
    const order = store.addNewOrder();
    const resourcePm = store.models["pos.payment.method"].get(4);
    const date = DateTime.now();

    await store.addLineToOrder(
        {
            product_tmpl_id: store.models["product.template"].get(5),
            qty: 1,
            write_date: date,
            create_date: date,
        },
        order
    );
    order.lines[0].sale_order_origin_id = { id: 1, name: "S00001" };

    const result = order.addPaymentline(resourcePm);
    expect(result.status).toBe(false);
    expect(typeof result.data).toBe("string");
});

test("addPaymentline - allowed when lines have no sale order origin", async () => {
    const store = await setupPosEnv();
    const order = store.addNewOrder();
    const resourcePm = store.models["pos.payment.method"].get(4);
    const date = DateTime.now();

    await store.addLineToOrder(
        {
            product_tmpl_id: store.models["product.template"].get(5),
            qty: 1,
            write_date: date,
            create_date: date,
        },
        order
    );

    const result = order.addPaymentline(resourcePm);
    expect(result.status).toBe(true);
});

test("addPaymentline - non-resource payment method is never blocked by sale order lines", async () => {
    const store = await setupPosEnv();
    const order = store.addNewOrder();
    const cashPm = store.models["pos.payment.method"].get(1);
    const date = DateTime.now();

    await store.addLineToOrder(
        {
            product_tmpl_id: store.models["product.template"].get(5),
            qty: 1,
            write_date: date,
            create_date: date,
        },
        order
    );
    order.lines[0].sale_order_origin_id = { id: 1, name: "S00001" };

    const result = order.addPaymentline(cashPm);
    expect(result.status).toBe(true);
});
