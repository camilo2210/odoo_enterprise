import { describe, test, expect } from "@odoo/hoot";
import { definePosPrepDisplayModels } from "@pos_enterprise/../tests/unit/data/generate_model_definitions";
import {
    setupPosPrepDisplayEnv,
    createPrepDisplayTicket,
} from "@pos_enterprise/../tests/unit/utils";

const { DateTime } = luxon;

definePosPrepDisplayModels();

test("toggleTime", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    expect(store.selectedTimeIds.size).toBe(0);
    store.toggleTime("tomorrow");
    expect(store.selectedTimeIds.has("tomorrow")).toBe(true);
});

test("togglePreset", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    expect(store.selectedPresetIds.size).toBe(0);
    store.togglePreset(1);
    expect(store.selectedPresetIds.has(1)).toBe(true);
});

describe("checkStateVisibility", () => {
    describe("no filters", () => {
        test("returns true for preparation line todo=true", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(true);
        });
        test("returns false for preparation line with todo=false", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            prepLine.todo = false;
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(true);
        });
    });

    describe("product category filter", () => {
        test("returns true for preparation line with products in selected category", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            store.toggleCategory(prepLine.categories[0]);
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(true);
        });

        test("returns false for preparation line with no products in selected category", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            const otherCategory = store.data.models["pos.category"]
                .getAll()
                .find((c) => !prepLine.categories.map((cat) => cat.id).includes(c.id));
            store.toggleCategory(otherCategory);
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(false);
        });
    });

    describe("product filter", () => {
        test("returns true for preparation line with selected products", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            prepLine.product.categoryIds = prepLine.categories.map((c) => c.id);
            store.toggleProduct(prepLine.product);
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(true);
        });

        test("returns false for preparation line with no selected products", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            const otherProduct = store.data.models["product.product"]
                .getAll()
                .find((p) => p.id !== prepLine.product.id);
            otherProduct.categoryIds = otherProduct.pos_categ_ids.map((c) => c.id);
            store.toggleProduct(otherProduct);
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(false);
        });
    });

    describe("time filter", () => {
        test("returns true for preparation line in selected time", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            store.toggleTime("today");
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(true);
        });

        test("returns false for preparation line not in selected time", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            store.toggleTime("yesterday");
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(false);
        });
        test("returns true when timeCheck is false but timeToShow is 0 and 'now' is selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            prepLine.timeToShow = 0;
            store.toggleTime("now");
            store.toggleTime("tomorrow"); // force timeCheck to fail
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(true);
        });

        test("returns false when timeToShow is not 0 even if 'now' is selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            prepLine.timeToShow = 10;
            store.toggleTime("now");
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(false);
        });
        test("returns true for order date two days in the future when 'next_days' is selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            prepLine.prep_order_id.pos_order_id.preset_time = DateTime.now().plus({
                days: 2,
            });
            store.toggleTime("next_days");
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(true);
        });

        test("returns false for tomorrow when only 'next_days' is selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            prepLine.prep_order_id.pos_order_id.preset_time = DateTime.now().plus({
                days: 1,
            });
            store.toggleTime("next_days");
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(false);
        });
        test("returns true when preset_time is missing and 'today' is selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            prepLine.prep_order_id.pos_order_id.preset_time = null;
            store.toggleTime("today");
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(true);
        });

        test("returns false when preset_time is missing and 'today' is not selected", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            prepLine.prep_order_id.pos_order_id.preset_time = null;
            store.toggleTime("tomorrow");
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(false);
        });
    });

    describe("preset filter", () => {
        test("returns true for preparation line with selected preset", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            const preset = store.data.models["pos.preset"].getAll()[0];
            prepLine.prep_order_id.pos_order_id.preset_id = preset;
            store.togglePreset(preset.id);
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(true);
        });

        test("returns false for preparation linepreparation line with no selected preset", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            const preset = store.data.models["pos.preset"].getAll()[0];
            prepLine.prep_order_id.pos_order_id.preset_id = preset;
            const otherPreset = store.data.models["pos.preset"]
                .getAll()
                .find((p) => p.id !== preset.id);
            store.togglePreset(otherPreset.id);
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(false);
        });

        test("returns false when a preset is selected but preparation line has no preset_id", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);
            const prepLine = store.data.models["pos.prep.line"].getAll()[0];
            const preset = store.data.models["pos.preset"].getAll()[0];
            store.togglePreset(preset.id);
            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(false);
        });
    });

    describe("combined filters", () => {
        test("returns false when one of multiple active filters does not match", async () => {
            const store = await setupPosPrepDisplayEnv();
            await createPrepDisplayTicket(store);

            const prepLine = store.data.models["pos.prep.line"].getAll()[0];

            // Matching category
            store.toggleCategory(prepLine.categories[0]);

            // Non-matching product
            const otherProduct = store.data.models["product.product"]
                .getAll()
                .find((p) => p.id !== prepLine.product.id);
            otherProduct.categoryIds = otherProduct.pos_categ_ids.map((c) => c.id);
            store.toggleProduct(otherProduct);

            const visible = store.checkStateVisibility(prepLine);
            expect(visible).toBe(false);
        });
    });
});

describe("orderNextStage", () => {
    test("returns next stage for given stage id", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const stages = store.data.models["pos.prep.stage"].getAll();
        const nextStage = store.orderNextStage(stages[0].id);
        expect(nextStage.id).toBe(stages[1].id);
    });

    test("returns first stage if current is last", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const lastStage = store.lastStage;
        const firstStage = store.orderNextStage(lastStage.id);
        expect(firstStage.id).toBe(store.data.models["pos.prep.stage"].getAll()[0].id);
    });
});

test("doneOrders", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const prepLines = store.data.models["pos.prep.line"].getAll();
    await store.doneOrders(prepLines);
    expect(prepLines.every((s) => s.todo === false)).toBe(true);
});

test("changeStateStage", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const prepLines = store.data.models["pos.prep.line"].getAll();
    await store.changeStateStage(prepLines);
    await store.data.initData();
    expect(store.data.models["pos.prep.line"].getAll()[0].stage_id.id).toBe(2);
});

test("filteredOrders", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const prepLines = store.data.models["pos.prep.line"].getAll();
    expect(store.filteredOrders.length).toBe(1);
    await store.changeStateStage(prepLines);
    await store.data.initData();
    expect(store.filteredOrders.length).toBe(0);
});

test("[removeOrdersByPosOrderIds] removes POS order and related preparation records", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const models = store.data.models;
    const posOrder = models["pos.order"].getFirst();

    expect(models["pos.order"].length).toBe(1);
    expect(models["pos.prep.order"].length).toBe(1);
    expect(models["pos.prep.line"].length).toBe(2);
    expect(models["pos.prep.line"].length).toBe(2);

    store.removeOrdersByPosOrderIds([posOrder.id]);
    expect(models["pos.order"].length).toBe(0);
    expect(models["pos.prep.order"].length).toBe(0);
    expect(models["pos.prep.line"].length).toBe(0);
    expect(models["pos.prep.line"].length).toBe(0);
});

test("moveAllOrdersToNextStage -> when order not in lastStage", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    await store.moveAllOrdersToNextStage();
    await store.data.initData();
    const prepLines = store.data.models["pos.prep.line"].getAll();
    expect(prepLines[0].stage_id.id).toBe(2);
});

test("moveAllOrdersToNextStage -> when order is in lastStage", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const orders = store.filteredOrders;
    orders[0].stage = store.lastStage;
    await store.moveAllOrdersToNextStage();
    expect(orders[0].prepLines.every((s) => s.todo === false)).toBe(true);
});
