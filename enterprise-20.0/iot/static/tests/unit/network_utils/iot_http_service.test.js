import { beforeEach, describe, expect, mockFetch, test } from "@odoo/hoot";
import { defineModels, makeTestApp, models } from "@web/../tests/web_test_helpers";
import { uuid } from "@web/core/utils/strings";

import { IotHttpService } from "@iot/network_utils/iot_http_service";

describe.current.tags("headless");

class IotChannel extends models.Model {
    get_iot_channel() {
        return "mockChannel";
    }
}

defineModels({ IotChannel });

class DummyOrm {
    async searchRead(model, domain, _fields) {
        const [[, , iotBoxId]] = domain;
        if (iotBoxId === 1) {
            return [{ id: iotBoxId, ip: "127.0.0.1", identifier: "box-123" }];
        }
        return [{ id: iotBoxId, ip: "127.0.0.1", identifier: "box-456" }];
    }
}

let iotHttpService;
let websocketMessages;
let notification;
let longpolling;
let websocket;
let orm;
let onSuccess;
let onFailure;
let calledCallback;

beforeEach(async () => {
    await makeTestApp();
    websocketMessages = [];
    notification = {
        added: [],
        add: function (msg, opts) {
            this.added.push({ msg, opts });
        },
    };

    orm = new DummyOrm({ ip: "127.0.0.1", identifier: "box-123" });

    mockFetch(() => true);

    // reset callback tracker
    calledCallback = "pending";

    // if we should receive a failed response from the IoT Box
    let longpollingShouldFail = false;
    let websocketShouldFail = false;

    // if calling the action should fail
    let longpollingShouldThrow = false;
    let websocketShouldThrow = false;

    // longpolling should respond like a standard http request, or be delayed like longpolling
    let longpollingDirectResponse = true;

    longpolling = {
        directResponse: false,
        sendMessage: async (ip, payload, actionId, _hasFallback) => {
            if (longpollingShouldThrow) {
                throw new Error("longpolling sendMessage failed");
            }
            return {
                status: longpollingShouldFail ? "error" : "success",
                result: !longpollingDirectResponse ? "pending" : {},
            };
        },
        onMessage: (ip, deviceIdentifier, onSuccess, onFailure, actionId) => {
            if (longpollingShouldThrow) {
                throw new Error("longpolling onMessage failed");
            }
            if (longpollingShouldFail) {
                onFailure({ status: "disconnected" }, deviceIdentifier);
                return;
            }
            onSuccess({ status: "success", device_identifier: deviceIdentifier }, deviceIdentifier);
        },
        setThrow: (v) => {
            longpollingShouldThrow = v;
        },
        setFail: (v) => {
            longpollingShouldFail = v;
        },
        shouldRespondDirectly: (v) => {
            longpollingDirectResponse = v;
        },
    };

    websocket = {
        sendMessage: async (identifier, payload, actionId, messageType) => {
            if (websocketShouldThrow) {
                throw new Error("websocket sendMessage failed");
            }
            websocketMessages.push({ identifier, payload, actionId, messageType });
            return actionId || uuid();
        },
        onMessage: (
            identifier,
            deviceIdentifier,
            onSuccess,
            onFailure,
            _messageType,
            _actionId
        ) => {
            if (websocketShouldThrow) {
                throw new Error("websocket onMessage failed");
            }
            if (websocketShouldFail) {
                onFailure({ status: "disconnected" }, deviceIdentifier);
                return;
            }
            onSuccess({ status: "success", device_identifier: deviceIdentifier }, deviceIdentifier);
        },
        setThrow: (v) => {
            websocketShouldThrow = v;
        },
        setFail: (v) => {
            websocketShouldFail = v;
        },
    };

    onSuccess = () => {
        calledCallback = "onSuccess";
    };
    onFailure = () => {
        calledCallback = "onFailure";
    };

    iotHttpService = new IotHttpService({
        iot_longpolling: longpolling,
        websocket,
        notification,
        orm,
    });
});

describe("action", () => {
    describe("longpolling", () => {
        test("uses /action response and succeeds", async () => {
            longpolling.shouldRespondDirectly(true);
            await iotHttpService.action(1, "device-2", { a: "b" }, onSuccess, onFailure);

            expect(calledCallback).toBe("onSuccess");
            expect(iotHttpService.connectionStatus).toBe("longpolling");
        });

        test("waits for /event and succeeds", async () => {
            longpolling.shouldRespondDirectly(false);
            await iotHttpService.action(1, "device-2", { a: "b" }, onSuccess, onFailure);

            expect(calledCallback).toBe("onSuccess");
            expect(iotHttpService.connectionStatus).toBe("longpolling");
        });
    });

    test("fallback to websocket when longpolling fails", async () => {
        longpolling.setThrow(true);

        await iotHttpService.action(1, "device-3", { x: "y" }, onSuccess, onFailure);
        expect(calledCallback).toBe("onSuccess");
        expect(iotHttpService.connectionStatus).toBe("websocket");
    });

    test("all methods fail and onFailure is invoked with disconnected status", async () => {
        longpolling.setThrow(true);
        websocket.setThrow(true);

        await iotHttpService.action(1, "device-4", { something: "else" }, onSuccess, onFailure);
        expect(calledCallback).toBe("onFailure");
        expect(iotHttpService.connectionStatus).toBe("offline");
    });

    test("invalid iotBoxId (get id from Many2one)", async () => {
        await iotHttpService.action({ id: 1 }, "device-array", { foo: "bar" }, onSuccess);
        expect(calledCallback).toBe("onSuccess");
    });

    test("longpolling onMessage calls back onFailure", async () => {
        longpolling.setFail(true); // make longpolling onMessage report failure
        await iotHttpService.action(
            1,
            "device-longpolling-fail",
            { foo: "bar" },
            onSuccess,
            onFailure
        );
        expect(calledCallback).toBe("onFailure");
        expect(iotHttpService.connectionStatus).toBe("longpolling"); // received failure callback from longpolling
    });

    test("websocket onMessage calls back onFailure", async () => {
        longpolling.setThrow(true);
        websocket.setFail(true); // make websocket onMessage report failure
        await iotHttpService.action(
            1,
            "device-websocket-fail",
            { foo: "bar" },
            onSuccess,
            onFailure
        );
        expect(calledCallback).toBe("onFailure");
        expect(iotHttpService.connectionStatus).toBe("websocket"); // received failure callback from websocket
    });

    test("IoT Box records were cached after success, then removed after failure", async () => {
        await iotHttpService.action(
            1,
            "device-2",
            { a: "attempt-1-succeeds" },
            onSuccess,
            onFailure
        );
        await iotHttpService.action(
            2,
            "device-2",
            { a: "attempt-1-succeeds" },
            onSuccess,
            onFailure
        );
        expect(iotHttpService.cachedIotBoxes[1]?.identifier).toBe("box-123");
        expect(iotHttpService.cachedIotBoxes[2]?.identifier).toBe("box-456");

        // ensure that the second record (and only this one) is removed after failure
        longpolling.setThrow(true);
        websocket.setThrow(true);
        await iotHttpService.action(2, "device-2", { a: "attempt-2-fails" }, onSuccess, onFailure);
        expect(iotHttpService.cachedIotBoxes[1]?.identifier).toBe("box-123");
        expect(iotHttpService.cachedIotBoxes[2]).toBe(undefined);
    });
});
