import { test, expect } from "@odoo/hoot";
import { definePosPrepDisplayModels } from "@pos_enterprise/../tests/unit/data/generate_model_definitions";
import {
    setupPosPrepDisplayEnv,
    createPrepDisplayTicket,
} from "@pos_enterprise/../tests/unit/utils";
import { MockServer } from "@web/../tests/web_test_helpers";

definePosPrepDisplayModels();

test("quantities are rounded to the product unit precision", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store, {
        lines: [{ qty: 0.3, product_id: 5, full_product_name: "TEST" }],
    });
    const prepLine = store.data.models["pos.prep.line"].getAll()[0];
    prepLine.cancelled = 0.1;

    // 0.3 - 0.1 === 0.19999999999999998
    expect(prepLine.todoQuantity).toBe(0.2);
    expect(prepLine.roundedQuantity).toBe(0.3);
    expect(prepLine.roundedCancelled).toBe(0.1);
});

test("quantities follow the configured product unit precision", async () => {
    const store = await setupPosPrepDisplayEnv();
    const productUnit = MockServer.env["decimal.precision"].search([["name", "=", "Product Unit"]]);
    MockServer.env["decimal.precision"].write(productUnit, { digits: 3 });
    await createPrepDisplayTicket(store, {
        lines: [{ qty: 0.125, product_id: 5, full_product_name: "TEST" }],
    });
    const prepLine = store.data.models["pos.prep.line"].getAll()[0];

    // Would be 0.13 with the default precision of 2 decimals
    expect(prepLine.todoQuantity).toBe(0.125);
});
