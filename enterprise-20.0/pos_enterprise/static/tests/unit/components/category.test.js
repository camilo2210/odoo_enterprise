import { test, expect } from "@odoo/hoot";
import { definePosPrepDisplayModels } from "@pos_enterprise/../tests/unit/data/generate_model_definitions";
import {
    setupPosPrepDisplayEnv,
    createPrepDisplayTicket,
} from "@pos_enterprise/../tests/unit/utils";
import { Category } from "@pos_enterprise/app/components/category/category";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";

definePosPrepDisplayModels();

test("shouldShowCategory", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const category = store.data.models["pos.category"].getAll()[0];
    const comp = await mountWithCleanup(Category, { props: { category: category } });
    const result = comp.shouldShowCategory;
    expect(result).toBe(1);
    expect(comp.products.length).toBe(1);
});

test("preparation_display_service.toggleCategory", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const category = store.data.models["pos.category"].getAll()[0];
    await mountWithCleanup(Category, { props: { category: category } });
    // select category
    store.toggleCategory(category);
    expect(store.selectedCategoryIds.has(category.id)).toBe(true);
    expect(store.selectedProductIds.size).toBe(0);
    // unselect category
    store.toggleCategory(category);
    expect(store.selectedCategoryIds.has(category.id)).toBe(false);
});

test("preparation_display_service.toggleProduct", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const category = store.data.models["pos.category"].getAll()[0];
    const comp = await mountWithCleanup(Category, { props: { category: category } });
    const product = comp.products[0];
    // select product
    store.toggleProduct(product);
    expect(store.selectedProductIds.has(product.id)).toBe(true);
    expect(store.selectedCategoryIds.size).toBe(0);
    // unselect product
    store.toggleProduct(product);
    expect(store.selectedProductIds.has(product.id)).toBe(false);
});

test("accumulated quantities are rounded to the product unit precision", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store, {
        lines: [
            { qty: 0.1, product_id: 5, full_product_name: "TEST" },
            { qty: 0.2, product_id: 5, full_product_name: "TEST" },
        ],
    });
    const category = store.data.models["pos.category"].getAll()[0];
    const comp = await mountWithCleanup(Category, { props: { category: category } });
    expect(comp.shouldShowCategory).toBe(1);

    // 0.1 + 0.2 === 0.30000000000000004
    expect(comp.productCount).toBe(0.3);
    expect(comp.products[0].quantity).toBe(0.3);
});
