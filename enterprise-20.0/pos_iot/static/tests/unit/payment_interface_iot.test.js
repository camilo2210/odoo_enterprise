import { beforeEach, expect, test } from "@odoo/hoot";
import { mockService, onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { createPaymentLine, getFilledOrder, setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { PaymentInterfaceIot } from "@pos_iot/app/utils/payment/payment_interface_iot";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

class TestPaymentInterfaceIot extends PaymentInterfaceIot {
    getPaymentData(uuid) {
        return { cid: uuid };
    }
    getCancelData(uuid) {
        return { cid: uuid, cancel: true };
    }
    getPaymentLineForMessage(order, data) {
        return order.getPaymentlineByUuid(data.cid);
    }
    onTerminalMessageReceived(data, line) {
        this.messagesReceived = (this.messagesReceived || 0) + 1;
        if (data.cancel) {
            this._resolveCancellation?.(true);
        } else {
            this._resolvePayment?.(data.success);
        }
    }
}

definePosModels();

let actionCalls;
let onMessageCalls;

beforeEach(() => {
    onRpc("/iot_drivers/action", () => true);
    onRpc("/iot_drivers/event", () => true);
    patchWithCleanup(console, { log: () => {} });

    // Fonts
    onRpc("/css", () => "");
    onRpc("/fonts/*", () => "");
    onRpc("/point_of_sale/static/*", () => "");
    onRpc("/web/static/*", () => "");

    actionCalls = [];
    onMessageCalls = 0;
    mockService("iot_http", {
        action: async (iotId, identifier, data, onSuccess, onFailure) => {
            actionCalls.push({ iotId, identifier, data, onSuccess, onFailure });
        },
        onMessage: async () => {
            onMessageCalls++;
        },
    });
});

const getInterface = async (paymentMethodId = 5) => {
    const store = await setupPosEnv();
    const order = await getFilledOrder(store);
    const pm = store.models["pos.payment.method"].get(paymentMethodId);
    const line = createPaymentLine(store, order, pm);
    const iface = new TestPaymentInterfaceIot(store, pm);
    return { order, line, iface };
};

test("sendPaymentRequest sends the payment data and resolves on a matching success message", async () => {
    const { order, line, iface } = await getInterface();

    const promise = iface.sendPaymentRequest(line);
    expect(iface.transactionInProgress).toBe(true);
    expect(actionCalls).toHaveLength(1);
    expect(actionCalls[0].data).toEqual({ cid: line.uuid });

    iface._onValueChange(order, { cid: line.uuid, success: true });
    expect(await promise).toBe(true);
    expect(iface.transactionInProgress).toBe(false);
});

test("sendPaymentCancel sends the cancel data and resolves the cancellation", async () => {
    const { order, line, iface } = await getInterface();

    const promise = iface.sendPaymentCancel(line);
    expect(actionCalls).toHaveLength(1);
    expect(actionCalls[0].data).toEqual({ cid: line.uuid, cancel: true });

    iface._onValueChange(order, { cid: line.uuid, cancel: true });
    expect(await promise).toBe(true);
    expect(iface.transactionInProgress).toBe(false);
});

test("sendPaymentRequest without a configured terminal shows an error and resolves false", async () => {
    let dialogAdded = null;
    mockService("dialog", {
        add: (dialogClass, props) => {
            dialogAdded = { dialogClass, props };
            return () => {};
        },
    });
    const { line, iface } = await getInterface(6);

    const result = await iface.sendPaymentRequest(line);
    expect(result).toBe(false);
    expect(actionCalls).toHaveLength(0);
    expect(dialogAdded.dialogClass).toBe(AlertDialog);
    expect(dialogAdded.props.title.toString()).toBe("Configuration of payment terminal failed");
});

test("_onActionFail with a timeout status keeps listening without resolving", async () => {
    const { order, line, iface } = await getInterface();

    const promise = iface.sendPaymentRequest(line);
    iface._onActionFail({ status: "timeout" });
    expect(iface.transactionInProgress).toBe(true);
    expect(onMessageCalls).toBe(1);

    iface._onValueChange(order, { cid: line.uuid, success: true });
    expect(await promise).toBe(true);
});

test("_onActionFail with a disconnected status fails the payment and shows a dialog", async () => {
    let dialogAdded = null;
    mockService("dialog", {
        add: (dialogClass, props) => {
            dialogAdded = { dialogClass, props };
            return () => {};
        },
    });
    const { line, iface } = await getInterface();

    const promise = iface.sendPaymentRequest(line);
    iface._onActionFail({ status: "disconnected" });

    expect(await promise).toBe(false);
    expect(iface.transactionInProgress).toBe(false);
    expect(dialogAdded.dialogClass).toBe(AlertDialog);
    expect(dialogAdded.props.title.toString()).toBe("Connection to terminal failed");
});

test("_onValueChange ignores a message that doesn't match any payment line", async () => {
    const { order, line, iface } = await getInterface();

    iface.sendPaymentRequest(line);
    iface._onValueChange(order, { cid: "unknown-uuid", success: true });
    expect(iface.messagesReceived).toBeEmpty();
});

test("_onValueChange ignores a message when there is no transaction in progress", async () => {
    const { order, line, iface } = await getInterface();

    expect(iface.transactionInProgress).toBeEmpty();
    iface._onValueChange(order, { cid: line.uuid, success: true });
    expect(iface.messagesReceived).toBeEmpty();
});
