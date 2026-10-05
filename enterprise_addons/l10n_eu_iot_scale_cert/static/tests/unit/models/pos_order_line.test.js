import { test, expect } from "@odoo/hoot";
import { getFilledOrder, setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

test("Deleted (struck-through) line is never merged with a new one", async () => {
    const store = await setupPosEnv();
    const order = await getFilledOrder(store);
    const line1 = order.lines[0];
    const line2 = order.lines[1];

    line2.product_id = line1.product_id;
    line2.setFullProductName(line1.full_product_name);
    expect(line1.canBeMergedWith(line2)).toBe(true);

    line1.uiState.isDeleted = true;
    line1.setQuantity(0);
    expect(line1.uiState.isDeleted).toBe(true);
    expect(line1.qty).toBe(0);

    expect(line1.canBeMergedWith(line2)).toBe(false);
    expect(line2.canBeMergedWith(line1)).toBe(false);

    line1.uiState.isDeleted = false;
    expect(line1.canBeMergedWith(line2)).toBe(true);
});

test("Re-adding a removed product creates a new line instead of reviving the old one", async () => {
    const store = await setupPosEnv();
    const order = await getFilledOrder(store);
    const line1 = order.lines[0];
    const initialLineCount = order.lines.length;

    line1.uiState.isDeleted = true;
    line1.uiState.deletedWeightQuantityStr = line1.quantityStr;
    line1.setQuantity(0);

    await store.addLineToOrder(
        { product_tmpl_id: line1.product_id.product_tmpl_id, qty: 3 },
        order
    );

    expect(order.lines.length).toBe(initialLineCount + 1);

    const newLine = order.lines.find(
        (l) => l.id !== line1.id && l.product_id.id === line1.product_id.id
    );
    expect(newLine).not.toBe(undefined);
    expect(newLine.qty).toBe(3);
    expect(newLine.uiState.isDeleted).toBe(false);

    expect(line1.uiState.isDeleted).toBe(true);
    expect(line1.qty).toBe(0);
});
