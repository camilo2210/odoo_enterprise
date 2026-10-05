import { IoTLongpolling } from "@iot/network_utils/iot_longpolling";
import { beforeEach, describe, expect, mockFetch, test, waitUntil } from "@odoo/hoot";
import { allowTranslations } from "@web/../tests/web_test_helpers";

describe.current.tags("headless");

const notificationsReceived = [];
beforeEach(() => notificationsReceived.splice(0));

const mockServices = {
    notification: { add: (title) => notificationsReceived.push(title) },
};
const mockIp = "1.2.3.4";

const mockActionResponse = (options = {}) => {
    mockFetch((path, { body }) => {
        const url = new URL(path);
        const expectedRoute = options.route ?? "/iot_drivers/action";
        if (url.pathname === expectedRoute && url.hostname === mockIp) {
            if (options.shouldThrowError) {
                throw new Error();
            }
            return JSON.parse(body).params;
        }
    });
};

const mockEventResponse = (events, options = {}) => {
    const eventsRemaining = [...events];
    mockFetch((path, { body }) => {
        const url = new URL(path);
        if (url.pathname === "/iot_drivers/event" && url.hostname === mockIp) {
            if (options.shouldThrowError) {
                throw new Error();
            }
            if (eventsRemaining.length === 0) {
                return new Promise(() => {});
            }
            const [event] = eventsRemaining.splice(0, 1);
            const listener = JSON.parse(body).params.listener;
            return {
                result: {
                    status: options.customStatus ?? "success",
                    session_id: listener.session_id,
                    device_identifier: event,
                },
            };
        }
    });
};

describe("rpc", () => {
    test("returns action result", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        mockActionResponse();

        const result = await longpolling.rpc(mockIp, {
            device_identifier: "mockDevice",
            data: "testData",
        });

        expect(result.data).toBe("testData");
        expect(result.device_identifier).toBe("mockDevice");
    });

    test("throws if network error occurs", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        mockActionResponse({ shouldThrowError: true });

        const resultPromise = longpolling.rpc(mockIp, {
            device_identifier: "mockDevice",
            data: "testData",
        });

        await expect(resultPromise).rejects.toBeInstanceOf(Error);
    });

    test("shows failure notification", async () => {
        allowTranslations();

        const longpolling = new IoTLongpolling(mockServices);
        mockActionResponse({ shouldThrowError: true });

        const resultPromise = longpolling.rpc(mockIp, {
            device_identifier: "mockDevice",
            data: "testData",
        });

        await expect(resultPromise).rejects.toThrow(Error);
        expect(notificationsReceived).toHaveLength(1);
        expect(notificationsReceived[0]).toMatch(mockIp);
    });

    test("does not show failure notification when fallback=true", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        mockActionResponse({ shouldThrowError: true });

        const resultPromise = longpolling.rpc(
            mockIp,
            {
                device_identifier: "mockDevice",
                data: "testData",
            },
            {
                fallback: true,
            }
        );

        await expect(resultPromise).rejects.toBeInstanceOf(Error);
        expect(notificationsReceived).toHaveLength(0);
    });
});

describe("addListener", () => {
    test("receives an event", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        const eventsReceived = [];
        mockEventResponse(["mockDevice"]);

        longpolling.addListener(mockIp, ["mockDevice"], "testListenerId", (event) =>
            eventsReceived.push(event)
        );

        await waitUntil(() => eventsReceived.length === 1);
        expect(eventsReceived[0].device_identifier).toBe("mockDevice");
    });

    test("receives multiple events", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        const eventsReceived = [];
        mockEventResponse(["mockDevice", "mockDevice"]);

        longpolling.addListener(mockIp, ["mockDevice"], "testListenerId", (event) =>
            eventsReceived.push(event)
        );

        await waitUntil(() => eventsReceived.length === 2);
        expect(eventsReceived[0].device_identifier).toBe("mockDevice");
        expect(eventsReceived[1].device_identifier).toBe("mockDevice");
    });

    test("ignores other device events", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        const eventsReceived = [];
        mockEventResponse(["otherDevice", "mockDevice"]);

        longpolling.addListener(mockIp, ["mockDevice"], "testListenerId", (event) =>
            eventsReceived.push(event)
        );

        await waitUntil(() => eventsReceived.length === 1);
        expect(eventsReceived[0].device_identifier).toBe("mockDevice");
    });

    test("receives events for multiple devices", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        const eventsReceived = [];
        mockEventResponse(["mockDevice2", "mockDevice"]);

        longpolling.addListener(mockIp, ["mockDevice", "mockDevice2"], "testListenerId", (event) =>
            eventsReceived.push(event)
        );

        await waitUntil(() => eventsReceived.length === 2);
        expect(eventsReceived[0].device_identifier).toBe("mockDevice2");
        expect(eventsReceived[1].device_identifier).toBe("mockDevice");
    });

    test("aborts previous request when adding new listener", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        mockEventResponse([]);

        longpolling.addListener(mockIp, ["mockDevice"], "testListenerId");
        const firstAbortController = longpolling._listeners[mockIp].abortController;
        longpolling.addListener(mockIp, ["mockDevice2"], "testListenerId");
        const secondAbortController = longpolling._listeners[mockIp].abortController;

        expect(firstAbortController.signal.aborted).toBe(true);
        expect(secondAbortController.signal.aborted).toBe(false);
    });

    test("returns unreachable error when network request fails", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        const eventsReceived = [];
        mockEventResponse([], { shouldThrowError: true });

        longpolling.addListener(mockIp, ["mockDevice"], "testListenerId", (event) =>
            eventsReceived.push(event)
        );

        await waitUntil(() => eventsReceived.length === 1);
        expect(eventsReceived[0]).toMatchObject({ status: "unreachable" });
    });
});

describe("removeListener", () => {
    test("stops listening for events", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        const eventsReceived = [];
        mockEventResponse(["mockDevice", "mockDevice"]);

        longpolling.addListener(mockIp, ["mockDevice"], "testListenerId", (event) => {
            longpolling.removeListener(mockIp, "mockDevice", "testListenerId");
            eventsReceived.push(event);
        });

        await waitUntil(() => eventsReceived.length === 1);
        expect(longpolling._listeners[mockIp].devices).toBeEmpty();
        expect(longpolling._listeners[mockIp].abortController).toBe(null);
    });

    test("keeps polling if there is still a device listening", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        const eventsReceived = [];
        mockEventResponse(["mockDevice"]);

        longpolling.addListener(mockIp, ["mockDevice"], "testListenerId", (event) => {
            longpolling.removeListener(mockIp, "mockDevice", "testListenerId");
            eventsReceived.push(event);
        });
        longpolling.addListener(mockIp, ["mockDevice2"], "testListenerId2");

        await waitUntil(() => eventsReceived.length === 1);
        expect(longpolling._listeners[mockIp].devices).toInclude("mockDevice2");
        expect(longpolling._listeners[mockIp].abortController).not.toBe(null);
    });
});

describe("onMessage", () => {
    test("passes all arguments to addListener", () => {
        const longpolling = new IoTLongpolling(mockServices);
        mockEventResponse([]);

        longpolling.onMessage(
            mockIp,
            "mockDevice",
            () => {},
            () => {},
            "testSessionId",
            true
        );

        expect(longpolling._listeners[mockIp]).toBeOfType("object");
        expect(longpolling._listeners[mockIp].devices).toHaveLength(1);
        expect(longpolling._listeners[mockIp].devices["mockDevice"]).toBeOfType("object");
        expect(longpolling._listeners[mockIp].session_id).toBe("testSessionId");
        expect(longpolling._listeners[mockIp].useLna).toBe(true);
    });

    test("calls success callback on 'success' status", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        mockEventResponse(["mockDevice"]);
        let successCallbackCalled = false;
        let failureCallbackCalled = false;

        longpolling.onMessage(
            mockIp,
            "mockDevice",
            () => (successCallbackCalled = true),
            () => (failureCallbackCalled = true)
        );

        await waitUntil(() => successCallbackCalled);
        expect(failureCallbackCalled).toBe(false);
    });

    test("calls failure callback on non-'success' status", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        mockEventResponse(["mockDevice"], { customStatus: "failure" });
        let successCallbackCalled = false;
        let failureCallbackCalled = false;

        longpolling.onMessage(
            mockIp,
            "mockDevice",
            () => (successCallbackCalled = true),
            () => (failureCallbackCalled = true)
        );

        await waitUntil(() => failureCallbackCalled);
        expect(successCallbackCalled).toBe(false);
    });

    test("stops listening after event is received", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        mockEventResponse(["mockDevice", "mockDevice"]);
        let successCallbackCalled = false;

        longpolling.onMessage(mockIp, "mockDevice", () => (successCallbackCalled = true));

        expect(longpolling._listeners[mockIp].devices["mockDevice"]).toBeOfType("object");
        await waitUntil(() => successCallbackCalled);
        expect(longpolling._listeners[mockIp].devices["mockDevice"]).toBe(undefined);
    });

    test("rejects if a network error occurs", async () => {
        const longpolling = new IoTLongpolling(mockServices);
        mockEventResponse([], { shouldThrowError: true });

        const promise = longpolling.onMessage(mockIp, "mockDevice");

        await expect(promise).rejects.toBeInstanceOf(Error);
    });
});
