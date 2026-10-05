import { test, expect } from "@odoo/hoot";
import { getFilledOrder, setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

test("createAmountPerPaymentTypeArray", async () => {
    // TODO: check this test and especially _createAmountPerPaymentTypeArray method
    // I think it is broken cause when there is change, change is negative so we should
    // add it as this.change and not -this.change in the amountPerPaymentTypeArray.
    const store = await setupPosEnv();
    const order = await getFilledOrder(store);
    const cashPaymentMethod = store.models["pos.payment.method"].get(1);
    order.addPaymentline(cashPaymentMethod);
    let result = order._createAmountPerPaymentTypeArray();
    expect(result).toEqual([{ payment_type: "CASH", amount: "17.85" }]);

    order.payment_ids[0].setAmount(10);
    result = order._createAmountPerPaymentTypeArray();
    expect(result).toEqual([{ payment_type: "CASH", amount: "10.00" }]);

    order.removePaymentline(order.payment_ids[0]);
    result = order._createAmountPerPaymentTypeArray();
    expect(result).toEqual([]);
});
