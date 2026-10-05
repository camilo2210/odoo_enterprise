import { test, expect } from "@odoo/hoot";
import { definePosPrepDisplayModels } from "@pos_enterprise/../tests/unit/data/generate_model_definitions";
import {
    setupPosPrepDisplayEnv,
    createPrepDisplayTicket,
} from "@pos_enterprise/../tests/unit/utils";
import { Orderline } from "@pos_enterprise/app/components/orderline/orderline";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";

definePosPrepDisplayModels();

test("attributeData does not crash when the line with a custom attribute is deleted", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store, {
        lines: [
            {
                qty: 1,
                product_id: 5,
                full_product_name: "Burger",
                attribute_value_ids: [7],
            },
        ],
    });
    const prepLine = store.data.models["pos.prep.line"].getAll()[0];
    store.data.models["product.attribute.custom.value"].create({
        custom_value: "no onions",
        custom_product_template_attribute_value_id:
            store.data.models["product.template.attribute.value"].get(7),
        pos_order_line_id: prepLine.pos_order_line_id,
        write_date: "2019-03-11 09:30:06",
    });
    prepLine.pos_order_line_id = undefined;

    const comp = await mountWithCleanup(Orderline, { props: { orderline: prepLine } });
    expect(comp.attributeData).toHaveLength(1);
    expect(comp.attributeData[0].name).toBe("Customization");
    expect(comp.attributeData[0].value).toBe("Yes");
});
