import { test, expect, describe } from "@odoo/hoot";
import { setupPosEnv, getFilledOrder } from "@point_of_sale/../tests/unit/utils";
import { click, waitFor } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

describe("onClickSaleOrder", () => {
    test("subscription_discount line treated as note", async () => {
        const store = await setupPosEnv();
        const order = await getFilledOrder(store);
        await mountWithCleanup(ProductScreen, { props: { orderUuid: order.uuid } });

        const promiseResult = store.onClickSaleOrder(3);
        await waitFor(".modal-body button:contains('Settle the order')");
        await click(".modal-body button:contains('Settle the order')");
        await promiseResult;
        expect(store.getOrder().lines[store.getOrder().lines.length - 1].customer_note).toBe(
            "These recurring products are discounted"
        );
    });
});
