import { discoverObox } from "@obox/client_actions/discover_obox";
import { describe, expect, mockFetch, test } from "@odoo/hoot";
import {
    makeTestApp,
    mockService,
    patchWithCleanup,
    runTestScope,
} from "@web/../tests/web_test_helpers";
import { location } from "@web/core/browser/browser";
import { ORM } from "@web/core/orm_plugin";

describe.current.tags("headless");

const setupMockEnv = async () => {
    mockService("notification", { add: (message) => expect.step(message) });
    mockService("action", { doAction: (action) => expect.step(action) });
    patchWithCleanup(ORM.prototype, {
        call(model, method, [pairingCode]) {
            if (model === "obox.obox" && method === "pair_obox" && pairingCode !== "ERROR") {
                expect.step("paired obox " + pairingCode);
                return 1;
            }
        },
    });
    await makeTestApp();
};

test("opens the offline popup if no Oboxes are found", async () => {
    await setupMockEnv();
    mockFetch(() => ({ result: [] }));

    await runTestScope(discoverObox);

    expect.verifySteps(["obox.action_obox_offline_connect_offline"]);
});

test("pairs the Obox if exactly one Obox is found", async () => {
    await setupMockEnv();
    mockFetch(() => ({ result: [{ pairing_code: "ABC", serial_number: "ODO123" }] }));

    await runTestScope(discoverObox);

    expect.verifySteps(["paired obox ABC"]);
    expect(location.pathname).toBe("/odoo/device/1");
});

test("pairs the first Obox if multiple are found", async () => {
    await setupMockEnv();
    mockFetch(() => ({
        result: [
            { pairing_code: "DEF", serial_number: "ODO123" },
            { pairing_code: "ABC", serial_number: "ODO456" },
        ],
    }));

    await runTestScope(discoverObox);

    expect.verifySteps(["paired obox DEF"]);
    expect(location.pathname).toBe("/odoo/device/1");
});

test("ignores any serials not starting with ODO", async () => {
    await setupMockEnv();
    mockFetch(() => ({
        result: [
            { pairing_code: "DEF", serial_number: "IOT123" },
            { pairing_code: "ABC", serial_number: "ODO456" },
        ],
    }));

    await runTestScope(discoverObox);

    expect.verifySteps(["paired obox ABC"]);
    expect(location.pathname).toBe("/odoo/device/1");
});

test("shows an error notification if pairing fails", async () => {
    await setupMockEnv();
    mockFetch(() => ({ result: [{ pairing_code: "ERROR", serial_number: "ODO123" }] }));

    await runTestScope(discoverObox);

    expect.verifySteps(["Failed to pair Obox ODO123"]);
});

test("shows an error notification if discover request fails", async () => {
    await setupMockEnv();
    mockFetch(() => {
        throw new Error();
    });

    await runTestScope(discoverObox);

    expect.verifySteps(["Failed to discover Oboxes on local network"]);
});
