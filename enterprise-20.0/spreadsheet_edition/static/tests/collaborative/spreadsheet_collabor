import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { EventBus } from "@odoo/owl";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { makeSpreadsheetMockEnv } from "@spreadsheet/../tests/helpers/model";
import { SpreadsheetCollaborativeChannel } from "@spreadsheet_edition/bundle/o_spreadsheet/collaborative/spreadsheet_collaborative_channel";
import { getMockEnv, getService, mockService, onRpc } from "@web/../tests/web_test_helpers";

describe.current.tags("headless");
defineSpreadsheetModels();

async function setupEnvWithMockBus({ mockDispatch } = {}) {
    const channels = [];
    const _bus = new EventBus();

    const busService = {
        addChannel: (name) => {
            channels.push(name);
        },
        subscribe: (eventName, handler) => {
            _bus.addEventListener("notif", ({ detail }) => {
                if (detail.type === eventName) {
                    handler(detail.payload, { id: detail.id });
                }
            });
        },
        notify: (message) => {
            _bus.trigger("notif", message);
        },
    };
    const rpc =
        mockDispatch ||
        async function (request, params) {
            // Mock the server behavior: new revisions are pushed in the bus
            const documentId = Number(params.res_id);
            const message = (await request.json()).params.message;
            busService.notify({ type: "spreadsheet", payload: { id: documentId, ...message } });
            return { accepted: true };
        };
    onRpc("/spreadsheet/<string:res_model>/<int:res_id>/dispatch", rpc);
    mockService("bus_service", busService);
    await makeSpreadsheetMockEnv();
}

test("sending a message forward it to the registered listener", async function () {
    await setupEnvWithMockBus();
    const channel = new SpreadsheetCollaborativeChannel(getMockEnv(), "my.model", 5);
    let i = 5;
    channel.onNewMessage("anId", (message) => {
        expect.step("message");
        expect(message.greeting).toBe("hello", {
            message: "It should have the correct message content",
        });
        i = 8;
    });
    await channel.sendMessage({ greeting: "hello" });
    expect(i).toBe(8);
    // It should have received the message
    expect.verifySteps(["message", "message"]); // The message is handled twice because the server's response says it is accepted, and a second time when it comes back throught the websocket
});

test("previous messages are forwarded when registering a listener", async function () {
    await setupEnvWithMockBus();
    const channel = new SpreadsheetCollaborativeChannel(getMockEnv(), "my.model", 5);
    await channel.sendMessage({ greeting: "hello" });
    channel.onNewMessage("anId", (message) => {
        expect.step("message");
        expect(message.greeting).toBe("hello", {
            message: "It should have the correct message content",
        });
    });
    // It should have received the pending message
    expect.verifySteps(["message", "message"]);
});

test("the channel does not care about other bus messages", async function () {
    await setupEnvWithMockBus();
    const channel = new SpreadsheetCollaborativeChannel(getMockEnv(), "my.model", 5);
    channel.onNewMessage("anId", () => expect.step("message"));
    getService("bus_service").notify("a-random-channel", "a-random-message");
    await animationFrame();
    // The message should not have been received
    expect.verifySteps([]);
});

test("Message accepted by the server is immediately handled", async function () {
    await setupEnvWithMockBus({
        mockDispatch: async function (request, params) {
            // Mock the server to accept the revision
            return { accepted: true };
        },
    });
    const channel = new SpreadsheetCollaborativeChannel(getMockEnv(), "my.model", 5);
    channel.onNewMessage("anId", (message) => {
        expect.step("message");
        expect(message.greeting).toBe("hello");
    });
    channel.sendMessage({ greeting: "hello" });
    await animationFrame();
    expect.verifySteps(["message"]);
});

test("Message refused by the server is not immediately handled", async function () {
    await setupEnvWithMockBus({
        mockDispatch: async function (request, params) {
            // Mock the server to refuse the revision
            return { accepted: false };
        },
    });
    const channel = new SpreadsheetCollaborativeChannel(getMockEnv(), "my.model", 5);
    channel.onNewMessage("anId", () => {
        expect.step("message");
    });
    channel.sendMessage({ greeting: "hello" });
    await animationFrame();
    expect.verifySteps([]);
});
