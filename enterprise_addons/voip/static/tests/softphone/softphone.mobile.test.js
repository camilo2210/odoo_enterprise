import { click, contains, insertText, start, startServer } from "@mail/../tests/mail_test_helpers";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { waitUntil } from "@odoo/hoot-dom";
import { mockUserAgent, tick } from "@odoo/hoot-mock";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { getService, patchWithCleanup, serverState } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";

describe.current.tags("mobile");
setupVoipTests();
beforeEach(() => mockUserAgent("android"));

test("mobile status menu only offers audio activation when the microphone has an error", async () => {
    await start();
    const voip = getService("voip");
    await voip.userAgent._audioManagerProm;
    await waitUntil(() => Boolean(voip.store.rtc.microphonePermission));
    voip.microphoneError = null;
    await tick();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click(".o-voip-StatusMenu-badge");

    await contains(".o-voip-StatusMenu-audioSettings", { count: 0 });
    await contains(".o-voip-StatusMenu-enableAudio", { count: 0 });

    voip.store.rtc.microphonePermission = "prompt";
    await tick();
    voip.microphoneError = "Microphone access has not been granted yet.";
    await tick();

    await contains(".o-voip-StatusMenu-enableAudio > .oi.text-danger", { text: "error" });
    await click(".o-voip-StatusMenu-enableAudio");
    await contains(".modal-footer .btn-secondary", { text: "Use microphone" });
});

test("mobile audio activation explains how to unblock the microphone", async () => {
    await start();
    const voip = getService("voip");
    await voip.userAgent._audioManagerProm;
    await waitUntil(() => Boolean(voip.store.rtc.microphonePermission));
    voip.store.rtc.microphonePermission = "denied";
    await tick();
    voip.microphoneError = "Microphone access is blocked.";
    await tick();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click(".o-voip-StatusMenu-badge");

    await contains(".o-voip-StatusMenu-enableAudio > .oi.text-danger", { text: "error" });
    await click(".o-voip-StatusMenu-enableAudio");

    await contains(".o-discuss-CallPermissionDeniedDialog");
    await contains(".o-discuss-CallPermissionDeniedDialog h2", {
        text: "Unable to access your microphone",
    });
});

test("Calls from the softphone use the native dialer when configured", async () => {
    patchWithCleanup(browser, {
        open(url) {
            expect.step(url);
        },
    });
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({
        how_to_call_on_mobile: "phone",
        user_id: serverState.userId,
    });
    await start();

    const voip = await getService("voip");
    await voip.userAgent.makeCall({ phone_number: "+1 202 555 0182" });

    expect.verifySteps(["tel:+12025550182"]);
});

test("Do nothing when user dismisses call method selection dialog", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({
        how_to_call_on_mobile: "ask",
        user_id: serverState.userId,
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input", "110");
    await click(".o-voip-Keypad-numpad button[title='Call']");
    await contains(".modal-dialog", { text: "Select a call method" });
    await click(".modal-header button[aria-label='Close']");
    // Ensure that the keypad is still there and the user can continue interacting with it
    await contains("body:not(:has(.modal-dialog)) .o-voip-Keypad");
    await click(".o-voip-Keypad-digitBtn span:text(1)");
    await contains(".o-voip-Keypad-searchBar input:value(1101)");
    await click(".o-voip-Keypad-digitBtn span:text(2)");
    await contains(".o-voip-Keypad-searchBar input:value(11012)");
});
