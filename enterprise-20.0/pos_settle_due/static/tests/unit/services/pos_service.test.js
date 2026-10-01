import { test, expect, describe } from "@odoo/hoot";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

describe("pos_store.js", () => {
    test("onClickDepositMoney", async () => {
        const store = await setupPosEnv();
        const randomPartner = store.models["res.partner"].getFirst();
        const expectedPaymentMethod = store.config.paymentMethods.find(
            (method) => method.type !== "pay_later"
        );
        const result = await store.onClickDepositMoney(50, randomPartner.id);
        const currentOrder = store.getOrder();
        const selectedPaymentLine = currentOrder.getSelectedPaymentline();

        expect(result).toBe(true);
        expect(currentOrder.payment_ids).toHaveLength(1);
        expect(selectedPaymentLine.amount).toBe(50);
        expect(selectedPaymentLine.payment_method_id).toBe(expectedPaymentMethod);
    });
});
