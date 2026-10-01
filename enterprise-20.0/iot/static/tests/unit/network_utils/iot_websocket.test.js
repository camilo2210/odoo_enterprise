import { beforeEach, describe, expect, runAllTimers, test, waitUntil } from "@odoo/hoot";
import { defineModels, getService, makeTestApp, models } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { EventBus } from "@odoo/owl";
import { IotWebsocket } from "@iot/network_utils/iot_websocket";

describe.current.tags("headless");

const sentWebsocketMessages = [];
const receivedWebsocketMessage = [];

class IotChannel extends models.Model {
    get_iot_channel() {
        return "mockChannel";
    }
    send_message(message, messageType) {
        sentWebsocketMessages.push({ message, messageType });
    }
}

defineMailModels(); // Only needed to prevent a 'discuss.channel' error on timeout test
defineModels({ IotChannel });

const setupWebsocket = async () => {
    const bus = new EventBus();
    const busCallbacks = new Map();
    const mockBusService = {
        addChannel: () => {},
        subscribe: (type, callback) => {
            busCallbacks.set(callback, (event) => callback(event.detail));
            bus.addEventListener(type, busCallbacks.get(callback));
        },
        unsubscribe: (type, callback) => bus.removeEventListener(type, busCallbacks.get(callback)),
        trigger: bus.trigger.bind(bus),
    };
    const websocket = new IotWebsocket({ bus_service: mockBusService, orm: getService("orm") });
    await waitUntil(() => !!websocket.iotChannel);
    return { websocket, bus };
};

beforeEach(async () => {
    await makeTestApp();
    sentWebsocketMessages.splice(0, sentWebsocketMessages.length);
    receivedWebsocketMessage.splice(0, receivedWebsocketMessage.length);
});

describe("setup", () => {
    test("gets the iot channel from the backend", async () => {
        const { websocket } = await setupWebsocket();

        expect(websocket.iotChannel).toBe("mockChannel");
    });
});

describe("sendMessage", () => {
    const testMessage = { testKey: "testValue" };

    test("sends message with identifier, session ID and action type", async () => {
        const { websocket } = await setupWebsocket();

        const result = await websocket.sendMessage("iot", testMessage);

        expect(sentWebsocketMessages).toHaveLength(1);
        expect(sentWebsocketMessages[0].message).toMatchObject(testMessage);
        expect(sentWebsocketMessages[0].message.iot_identifier).toBe("iot");
        expect(sentWebsocketMessages[0].message.session_id).toBeOfType("string");
        expect(sentWebsocketMessages[0].messageType).toBe("iot_action");
        expect(result).toBe(sentWebsocketMessages[0].message.session_id);
    });

    test("uses session ID if provided", async () => {
        const { websocket } = await setupWebsocket();

        const result = await websocket.sendMessage("iot", {}, "testSessionId");

        expect(sentWebsocketMessages).toHaveLength(1);
        expect(sentWebsocketMessages[0].message.session_id).toBe("testSessionId");
        expect(result).toBe("testSessionId");
    });

    test("uses message type if provided", async () => {
        const { websocket } = await setupWebsocket();

        await websocket.sendMessage("iot", testMessage, null, "testMessageType");

        expect(sentWebsocketMessages).toHaveLength(1);
        expect(sentWebsocketMessages[0].messageType).toBe("testMessageType");
    });
});

describe("onMessage", () => {
    const testMessage = { status: "success", testKey: "testValue" };

    test("receives message correctly", async () => {
        const { websocket, bus } = await setupWebsocket();

        websocket.onMessage("iot", "test_device", (message) =>
            receivedWebsocketMessage.push(message)
        );
        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot",
            device_identifier: "test_device",
            message: testMessage,
        });

        expect(receivedWebsocketMessage).toHaveLength(1);
        expect(receivedWebsocketMessage[0]).toEqual(testMessage);
    });

    test("ignores message if iot identifier is different", async () => {
        const { websocket, bus } = await setupWebsocket();

        websocket.onMessage("iot", "test_device", (message) =>
            receivedWebsocketMessage.push(message)
        );
        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot2",
            device_identifier: "test_device",
            message: testMessage,
        });

        expect(receivedWebsocketMessage).toHaveLength(0);
    });

    test("ignores message if device identifier is different", async () => {
        const { websocket, bus } = await setupWebsocket();

        websocket.onMessage("iot", "test_device", (message) =>
            receivedWebsocketMessage.push(message)
        );
        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot",
            device_identifier: "test_device2",
            message: testMessage,
        });

        expect(receivedWebsocketMessage).toHaveLength(0);
    });

    test("ignores message if session ID is different", async () => {
        const { websocket, bus } = await setupWebsocket();

        websocket.onMessage(
            "iot",
            "test_device",
            (message) => receivedWebsocketMessage.push(message),
            () => {},
            "operation_confirmation",
            "testSessionId"
        );
        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot",
            device_identifier: "test_device",
            message: testMessage,
            session_id: "badSessionId",
        });

        expect(receivedWebsocketMessage).toHaveLength(0);
    });

    test("receives message when session ID matches", async () => {
        const { websocket, bus } = await setupWebsocket();

        websocket.onMessage(
            "iot",
            "test_device",
            (message) => receivedWebsocketMessage.push(message),
            () => {},
            "operation_confirmation",
            "testSessionId"
        );
        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot",
            device_identifier: "test_device",
            message: testMessage,
            session_id: "testSessionId",
        });

        expect(receivedWebsocketMessage).toHaveLength(1);
        expect(receivedWebsocketMessage[0]).toEqual(testMessage);
    });

    test("calls failure callback on error", async () => {
        const { websocket, bus } = await setupWebsocket();
        let error = null;

        websocket.onMessage(
            "iot",
            "test_device",
            (message) => receivedWebsocketMessage.push(message),
            (message) => (error = message)
        );
        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot",
            device_identifier: "test_device",
            message: { status: "error" },
        });

        expect(receivedWebsocketMessage).toHaveLength(0);
        expect(error).toEqual({ status: "error" });
    });

    test("calls failure callback on timeout", async () => {
        const { websocket } = await setupWebsocket();
        let error = null;

        websocket.onMessage(
            "iot",
            "test_device",
            (message) => receivedWebsocketMessage.push(message),
            (message) => (error = message)
        );
        await runAllTimers();

        expect(receivedWebsocketMessage).toHaveLength(0);
        expect(error).toMatchObject({ status: "timeout" });
    });

    test("stops listening after receiving message", async () => {
        const { websocket, bus } = await setupWebsocket();

        websocket.onMessage("iot", "test_device", (message) =>
            receivedWebsocketMessage.push(message)
        );
        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot",
            device_identifier: "test_device",
            message: testMessage,
        });
        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot",
            device_identifier: "test_device",
            message: { ...testMessage, testKey: "anotherMessage" },
        });

        expect(receivedWebsocketMessage).toHaveLength(1);
        expect(receivedWebsocketMessage[0]).toEqual(testMessage);
    });

    test("ignores duplicate status and keeps listening for the real result", async () => {
        const { websocket, bus } = await setupWebsocket();
        let error = null;

        websocket.onMessage(
            "iot",
            "test_device",
            (message) => receivedWebsocketMessage.push(message),
            (message) => (error = message)
        );
        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot",
            device_identifier: "test_device",
            message: { status: "duplicate" },
        });

        expect(receivedWebsocketMessage).toHaveLength(0);
        expect(error).toBe(null);

        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot",
            device_identifier: "test_device",
            message: testMessage,
        });

        expect(receivedWebsocketMessage).toHaveLength(1);
        expect(receivedWebsocketMessage[0]).toEqual(testMessage);
    });

    test("a new listener supersedes a previous still-pending one for the same device", async () => {
        const { websocket, bus } = await setupWebsocket();
        const firstCalls = [];
        const secondCalls = [];

        websocket.onMessage(
            "iot",
            "test_device",
            (message) => firstCalls.push(message),
            (message) => firstCalls.push(message)
        );
        websocket.onMessage(
            "iot",
            "test_device",
            (message) => secondCalls.push(message),
            (message) => secondCalls.push(message)
        );
        bus.trigger("operation_confirmation", {
            iot_box_identifier: "iot",
            device_identifier: "test_device",
            message: testMessage,
        });

        // Only the second (latest) listener should have received the message.
        expect(firstCalls).toHaveLength(0);
        expect(secondCalls).toHaveLength(1);
        expect(secondCalls[0]).toEqual(testMessage);

        // The superseded listener's timeout must not fire either.
        await runAllTimers();
        expect(firstCalls).toHaveLength(0);
    });

    test("uses message type if provided", async () => {
        const { websocket, bus } = await setupWebsocket();

        websocket.onMessage(
            "iot",
            "test_device",
            (message) => receivedWebsocketMessage.push(message),
            () => {},
            "testMessageType"
        );
        bus.trigger("testMessageType", {
            iot_box_identifier: "iot",
            device_identifier: "test_device",
            message: testMessage,
        });

        expect(receivedWebsocketMessage).toHaveLength(1);
        expect(receivedWebsocketMessage[0]).toEqual(testMessage);
    });
});
