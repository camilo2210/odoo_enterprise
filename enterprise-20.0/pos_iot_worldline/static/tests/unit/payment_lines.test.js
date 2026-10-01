import { test, expect, describe } from "@odoo/hoot";
import {
    mockService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { setupPosEnv, getFilledOrder, createPaymentLine } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";

definePosModels();

const setupIot = () => {
    onRpc("/hw_drivers/action", () => true);
    onRpc("/iot_drivers/event", () => true);
    patchWithCleanup(console, { log: () => {} });

    onRpc("/css", () => "");
    onRpc("/fonts/*", () => "");
    onRpc("/web/static/*", () => "");

    mockService("iot_http", {
        action: async () => {},
        onMessage: async () => {},
    });
};

describe("delete button", () => {
    test("pending + test provider", async () => {
        setupIot();
        const store = await setupPosEnv();
        const order = await getFilledOrder(store);
        const card = store.models["pos.payment.method"].get(2);
        const paymentline = createPaymentLine(store, order, card);

        order.uiState.selected_paymentline_uuid = paymentline.uuid;
        card.payment_provider = "test_provider";
        paymentline.payment_status = "pending";

        await mountWithCleanup(PaymentScreenPaymentLines, {
            props: {
                paymentLines: [paymentline],
                deleteLine: () => {},
                selectLine: () => {},
                sendForceDone: () => {},
                sendForceCancel: () => {},
                sendPaymentCancel: () => {},
                sendPaymentRequest: () => {},
                updateSelectedPaymentline: () => {},
                isRefundOrder: false,
            },
        });
        expect(".paymentline button.delete-button").toHaveCount(1);
    });

    test("not selected but processing", async () => {
        setupIot();
        const store = await setupPosEnv();
        const order = await getFilledOrder(store);
        const card = store.models["pos.payment.method"].get(2);
        const paymentline = createPaymentLine(store, order, card);

        paymentline.payment_status = "waitingCard";

        await mountWithCleanup(PaymentScreenPaymentLines, {
            props: {
                paymentLines: [paymentline],
                deleteLine: () => {},
                selectLine: () => {},
                sendForceDone: () => {},
                sendForceCancel: () => {},
                sendPaymentCancel: () => {},
                sendPaymentRequest: () => {},
                updateSelectedPaymentline: () => {},
                isRefundOrder: false,
            },
        });
        expect(".paymentline i.oi-spin[data-icon='autorenew']").toHaveCount(1);
        expect(".paymentline button.delete-button").toHaveCount(0);
    });

    test("waitingCard + test provider", async () => {
        setupIot();
        const store = await setupPosEnv();
        const order = await getFilledOrder(store);
        const card = store.models["pos.payment.method"].get(2);
        const paymentline = createPaymentLine(store, order, card);

        order.uiState.selected_paymentline_uuid = paymentline.uuid;
        card.payment_provider = "test_provider";
        paymentline.payment_status = "waitingCard";

        await mountWithCleanup(PaymentScreenPaymentLines, {
            props: {
                paymentLines: [paymentline],
                deleteLine: () => {},
                selectLine: () => {},
                sendForceDone: () => {},
                sendForceCancel: () => {},
                sendPaymentCancel: () => {},
                sendPaymentRequest: () => {},
                updateSelectedPaymentline: () => {},
                isRefundOrder: false,
            },
        });
        expect(".paymentline button.delete-button").toHaveCount(1);
    });

    test("pending + worldline provider", async () => {
        setupIot();
        const store = await setupPosEnv();
        const order = await getFilledOrder(store);
        const card = store.models["pos.payment.method"].get(2);
        const paymentline = createPaymentLine(store, order, card);

        order.uiState.selected_paymentline_uuid = paymentline.uuid;
        card.payment_provider = "worldline";
        paymentline.payment_status = "pending";

        await mountWithCleanup(PaymentScreenPaymentLines, {
            props: {
                paymentLines: [paymentline],
                deleteLine: () => {},
                selectLine: () => {},
                sendForceDone: () => {},
                sendForceCancel: () => {},
                sendPaymentCancel: () => {},
                sendPaymentRequest: () => {},
                updateSelectedPaymentline: () => {},
                isRefundOrder: false,
            },
        });
        expect(".paymentline button.delete-button").toHaveCount(1);
    });

    test("waitingCard + worldline provider", async () => {
        setupIot();
        const store = await setupPosEnv();
        const order = await getFilledOrder(store);
        const card = store.models["pos.payment.method"].get(2);
        const paymentline = createPaymentLine(store, order, card);

        order.uiState.selected_paymentline_uuid = paymentline.uuid;
        card.payment_provider = "worldline";
        paymentline.payment_status = "waitingCard";

        await mountWithCleanup(PaymentScreenPaymentLines, {
            props: {
                paymentLines: [paymentline],
                deleteLine: () => {},
                selectLine: () => {},
                sendForceDone: () => {},
                sendForceCancel: () => {},
                sendPaymentCancel: () => {},
                sendPaymentRequest: () => {},
                updateSelectedPaymentline: () => {},
                isRefundOrder: false,
            },
        });
        expect(".paymentline button.delete-button").toHaveCount(0);
    });
});
