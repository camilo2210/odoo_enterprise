import { expect, test } from "@odoo/hoot";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { getFilledOrder, setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import {
    mockService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";

definePosModels();

test("pos_iot_payment_six", async () => {
    onRpc("/hw_drivers/action", () => true);
    onRpc("/iot_drivers/event", () => true);
    patchWithCleanup(console, { log: () => {} });

    // Fonts
    onRpc("/css", () => "");
    onRpc("/fonts/*", () => "");
    onRpc("/web/static/*", () => "");

    mockService("iot_http", {
        action: async () => {},
        onMessage: async () => {},
    });

    const store = await setupPosEnv();
    const order = await getFilledOrder(store);
    const sixPm = store.models["pos.payment.method"].find(
        (pm) => pm.payment_provider === "six_iot"
    );
    const pmScreen = await mountWithCleanup(PaymentScreen, {
        props: { orderUuid: order.uuid },
    });

    expect(sixPm.getPaymentInterfaceStates()).toEqual({
        status: true,
        message: "",
    });
    await pmScreen.addNewPaymentLine(sixPm);
    const pmLine = order.payment_ids.at(-1);
    pmScreen.sendPaymentRequest(pmLine);
    expect(sixPm.getPaymentInterfaceStates()).toEqual({
        status: false,
        message: "There is already an electronic payment in progress.",
    });
    expect(sixPm.payment_interface.terminal.iot_id?.id).toBe(2);

    const paymentData = sixPm.payment_interface.getPaymentData(pmLine.uuid);
    expect(paymentData.amount).toBe(Math.round(pmLine.amount * 100));
    expect(paymentData.cid).toBe(pmLine.uuid);

    const line = sixPm.payment_interface.getPaymentLineForMessage(order, {
        cid: pmLine.uuid,
    });
    expect(line).not.toBeEmpty();
    expect(line.amount).toBe(pmLine.amount);

    expect(pmLine.payment_status).toBe("waiting");
    await sixPm.payment_interface._resolvePayment(true);
    expect(pmLine.payment_status).toBe("done");
});
