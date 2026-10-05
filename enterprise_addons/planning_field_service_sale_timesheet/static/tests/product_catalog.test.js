import { describe, expect, test } from "@odoo/hoot";
import { click, queryAll } from "@odoo/hoot-dom";
import { advanceTime, runAllTimers } from "@odoo/hoot-mock";

import {
    contains,
    defineModels,
    getService,
    mountView,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { deepCopy } from "@web/core/utils/objects";
import { WebClient } from "@web/webclient/webclient";

import { ProductProduct } from "@planning_field_service_sale_timesheet/../tests/planning_field_service_sale_timesheet_mock_model";
import { projectModels } from "@project/../tests/project_models";
import { definePlanningModels, planningModels } from "@planning/../tests/planning_mock_models";
import { SaleOrder } from "@sale/../tests/mock_server/mock_models/sale_order";
import { SaleOrderLine } from "@sale/../tests/mock_server/mock_models/sale_order_line";
import { TimerTimer } from "@timer/../tests/timer_models";

const saleOrderLineInfo = {
    1: {
        quantity: 0,
        readOnly: false,
        price: 14,
        productType: "consu",
        uomDisplayName: "Unit",
        uomId: 1,
    },
    2: {
        quantity: 1,
        readOnly: false,
        price: 400,
        productType: "consu",
        uomDisplayName: "Unit",
        uomId: 1,
    },
    3: {
        quantity: 3,
        price: 70,
        readOnly: false,
        productType: "consu",
        uomDisplayName: "Unit",
        uomId: 1,
    },
};

planningModels.PlanningSlot._records = [{
    id: 1,
    name: "intervention",
    start_datetime: "2026-02-02 08:00:00",
    end_datetime: "2026-02-02 12:00:00",
}]

describe.current.tags("desktop");
defineModels({
    ProductProduct,
    SaleOrder,
    SaleOrderLine,
    TimerTimer,
    ...projectModels,
});
definePlanningModels();

onRpc("has_group", () => true);
onRpc("/product/catalog/order_lines_info", () => deepCopy(saleOrderLineInfo));

test("field_service_product_kanban widgets fetching data once", async () => {
    onRpc("/product/catalog/order_lines_info", () => {
        expect.step("fetch_sale_order_line_info");
        return deepCopy(saleOrderLineInfo);
    });

    await mountView({
        resModel: "product.product",
        type: "kanban",
        context: {
            product_catalog_order_model: "sale.order",
            intervention_id: 1,
        },
    });

    expect.verifySteps(["fetch_sale_order_line_info"]);
});

test("field_service_product_kanban widget in kanban view", async () => {
    await mountView({
        resModel: "product.product",
        type: "kanban",
        context: {
            product_catalog_order_model: "sale.order",
            intervention_id: 1,
        },
    });

    expect(queryAll(".o_kanban_view")).toHaveClass("o_field_service_product_kanban_view");
    expect(".o_kanban_record:not(.o_kanban_ghost)").toHaveCount(3, {
        message: "The number of kanban record should be equal to 3 records",
    });
    expect(
        ".o_kanban_record .o_product_catalog_buttons button:has(i[data-icon='shopping_cart'])"
    ).toHaveCount(1, {
        message:
            "The number of add button should be equal to the number of kanban records without any quantity (expected 1 records)",
    });
    expect(".o_kanban_record .o_product_catalog_quantity button:has(i[data-icon='add'])").toHaveCount(2, {
        message:
            "The number of increase button should be equal to the number of kanban records with a quantity set (expected 2 records)",
    });
    expect(".o_kanban_record .o_product_catalog_quantity button:has(i[data-icon='remove'])").toHaveCount(2, {
        message:
            "The number of decrease button should be equal to the number of kanban records with a quantity set (expected 2 records)",
    });
    const inputs = queryAll(".o_kanban_record .o_product_catalog_quantity input");
    expect(inputs.length).toBe(2, {
        message: "There should be one input space per record with quantity set (expected 2 inputs)",
    });
    expect(inputs[0]).toHaveValue(1);
    expect(inputs[1]).toHaveValue(3);
});

test("click on the minus/plus_buttons to decrease/increase the quantity of a product.", async () => {
    let firstPass = true;

    onRpc("/product/catalog/update_order_line_info", async (request) => {
        const { params } = await request.json();
        const { product_id, quantity } = params;
        expect.step("update_sale_order_line_info");
        if (product_id === 2) {
            if (firstPass) {
                expect(quantity).toBe(2, {
                    message:
                        "Using the plus button should increase the quantity by 1 unit in the route params (expected 2)",
                });
                firstPass = false;
            } else {
                expect(quantity).toBe(3, {
                    message:
                        "Clicking on the kanban card should increase the quantity by 1 unit in the route params (expected 3)",
                });
            }
        }
        if (product_id === 3) {
            expect(quantity).toBe(2, {
                message:
                    "Using the minus button should decrease the quantity by 1 unit in the route params (expected 2)",
            });
        }
        return {};
    });

    await mountView({
        resModel: "product.product",
        type: "kanban",
        context: {
            product_catalog_order_model: "sale.order",
            intervention_id: 1,
        },
    });

    await click(".o_kanban_record:nth-of-type(2) .o_product_catalog_quantity button:has(i[data-icon='add'])");
    await runAllTimers(); // for skipping the debounce delay
    expect(".o_kanban_record:nth-of-type(2) .o_product_catalog_quantity input").toHaveValue(2, {
        message:
            "Using the plus button should increase the product quantity by 1 unit (expected 2)",
    });

    await click(".o_kanban_record.o_product_added");
    await runAllTimers(); // for skipping the debounce delay
    expect(".o_kanban_record:nth-of-type(2) .o_product_catalog_quantity input").toHaveValue(3, {
        message:
            "Clicking on the kanban card should increase the product quantity by 1 unit (expected 3)",
    });

    await click(".o_kanban_record:nth-of-type(3) .o_product_catalog_quantity button:has(i[data-icon='remove'])");
    await runAllTimers(); // for skipping the debounce delay
    expect(".o_kanban_record:nth-of-type(3) .o_product_catalog_quantity input").toHaveValue(2, {
        message:
            "Clicking on the minus button should decrease the product quantity by 1 unit (expected 2)",
    });

    expect.verifySteps([
        "update_sale_order_line_info",
        "update_sale_order_line_info",
        "update_sale_order_line_info",
    ]);
});

test("check the debounce delay", async () => {
    onRpc("/product/catalog/update_order_line_info", async (request) => {
        const { params } = await request.json();
        const { product_id, quantity } = params;
        expect.step("update_sale_order_line_info");
        expect(quantity).toBe(4);
        expect(product_id).toBe(2);
        return { price: 100 };
    });

    await mountView({
        resModel: "product.product",
        type: "kanban",
        context: {
            product_catalog_order_model: "sale.order",
            intervention_id: 1,
        },
    });

    expect(".o_kanban_record:not(.o_kanban_ghost)").toHaveCount(3, {
        message: "The number of kanban record should be equal to 3 records",
    });

    await click(".o_kanban_record:nth-of-type(2) .o_product_catalog_quantity button:has(i[data-icon='add'])");
    await advanceTime(100); // click again before the debounce takes effect
    await click(".o_kanban_record:nth-of-type(2) .o_product_catalog_quantity button:has(i[data-icon='add'])");
    await advanceTime(100); // click again before the debounce takes effect
    await click(".o_kanban_record:nth-of-type(2) .o_product_catalog_quantity button:has(i[data-icon='add'])");
    await advanceTime(510); // wait until the debounce takes effect

    expect(".o_kanban_record:nth-of-type(2) .o_product_catalog_quantity input").toHaveValue(4);
    expect.verifySteps(["update_sale_order_line_info"]);
});

test("edit manually the product quantity and check Unit price update", async () => {
    onRpc("/product/catalog/update_order_line_info", async (request) => {
        const { params } = await request.json();
        const { product_id, quantity } = params;
        expect.step("update_sale_order_line_info");
        expect(quantity).toBe(12, {
            message: "The quantity should be set to 12 in the route params",
        });
        expect(product_id).toBe(2);
        return { price: 100 };
    });

    await mountView({
        resModel: "product.product",
        type: "kanban",
        context: {
            product_catalog_order_model: "sale.order",
            intervention_id: 1,
        },
    });

    expect('.o_kanban_record:nth-child(2) div[name="o_kanban_price"] span').toHaveText(
        "400.00",
        {
            message: "The Unit price should be equal to 400",
        }
    );
    expect(".o_kanban_record:nth-child(2) .o_product_catalog_quantity input").toHaveValue(1, {
        message: "The product quantity should be equal to 1",
    });

    await contains(".o_kanban_record:nth-child(2) .o_product_catalog_quantity input").edit(12);
    await runAllTimers(); // for skipping the debounce delay

    expect(".o_kanban_record:nth-child(2) .o_product_catalog_quantity input").toHaveValue(12, {
        message: "The product quantity should be equal to 12",
    });
    expect('.o_kanban_record:nth-child(2) div[name="o_kanban_price"] span').toHaveText(
        "100.00",
        {
            message: "The Unit price should be equal to 100 after the input change",
        }
    );
    expect.verifySteps(["update_sale_order_line_info"]);
});

test("edit manually a wrong product quantity", async () => {
    onRpc("/product/catalog/update_order_line_info", async (request) => {
        const { params } = await request.json();
        const { product_id, quantity } = params;
        expect.step("update_sale_order_line_info");
        if (product_id === 2) {
            expect(quantity).toBe(0, {
                message: "The quantity sent to the backend should be 0 if the input is 12a",
            });
        } else if (product_id === 3) {
            expect(quantity).toBe(0, {
                message: "The quantity sent to the backend should be 0 if the input is null",
            });
        }
        return {};
    });

    await mountView({
        resModel: "product.product",
        type: "kanban",
        context: {
            product_catalog_order_model: "sale.order",
            intervention_id: 1,
        },
    });

    await contains(".o_kanban_record:nth-child(2) .o_product_catalog_quantity input").fill(
        "12a"
    );
    await runAllTimers(); // for skipping the debounce delay

    expect(
        ".o_kanban_record:nth-child(2) .o_product_catalog_quantity button:has(i[data-icon='add'])"
    ).toHaveCount(0, {
        message:
            "After inputing a forbidden value, the quantity should be set to 0 and the plus button should disapear",
    });
    expect(
        ".o_kanban_record:nth-child(2) .o_product_catalog_quantity button:has(i[data-icon='remove'])"
    ).toHaveCount(0, {
        message:
            "After inputing a forbidden value, the quantity should be set to 0 and the minus button should disapear",
    });
    expect(".o_kanban_record:nth-child(2) .o_product_catalog_quantity input").toHaveCount(0, {
        message:
            "After inputing a forbidden value, the quantity should be set to 0 and the input space should disapear",
    });

    await contains(".o_kanban_record:nth-child(3) .o_product_catalog_quantity input").clear();
    await runAllTimers(); // for skipping the debounce delay

    expect(
        ".o_kanban_record:nth-child(2) .o_product_catalog_quantity button:has(i[data-icon='add'])"
    ).toHaveCount(0, {
        message:
            "After inputing a forbidden value, the quantity should be set to 0 and the plus button should disapear",
    });
    expect(
        ".o_kanban_record:nth-child(2) .o_product_catalog_quantity button:has(i[data-icon='remove'])"
    ).toHaveCount(0, {
        message:
            "After inputing a forbidden value, the quantity should be set to 0 and the minus button should disapear",
    });
    expect(".o_kanban_record:nth-child(2) .o_product_catalog_quantity input").toHaveCount(0, {
        message:
            "After inputing a forbidden value, the quantity should be set to 0 and the input space should disapear",
    });
    expect.verifySteps(["update_sale_order_line_info", "update_sale_order_line_info"]);
});


test("Test button 'Back to Shift'", async () => {
    ProductProduct._views.search = `<search/>`;
    planningModels.PlanningSlot._views.form = `<form><field name="name"/></form>`;
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "product.product",
        type: "ir.actions.act_window",
        views: [[false, "kanban"]],
        context: {
            product_catalog_order_model: "sale.order",
            active_model: "planning.slot",
            intervention_id: 1,
        },
    });

    expect("button.o-kanban-button-back").toBeDisplayed({
        message: "Button 'Back to intervention' should be displayed",
    });
    await click("button.o-kanban-button-back");
    await runAllTimers();
    expect(".o_form_view").toBeDisplayed({
        message: "It should lead to the shift form",
    });
});

test("Should display unit price with sales access", async () => {
    await mountView({
        resModel: "product.product",
        type: "kanban",
        context: {
            intervention_id: 1,
        },
    });
    expect(`.o_product_catalog_price`).toHaveCount(3, { message: "Unit price should be visible" });
});

test("Should not display unit price without any sales access", async () => {
    onRpc("has_group", () => false);
    await mountView({
        resModel: "product.product",
        type: "kanban",
        context: {
            intervention_id: 1,
        },
    });
    expect(`.o_product_catalog_price`).toHaveCount(0, { message: "Unit price should not be visible" });
});
