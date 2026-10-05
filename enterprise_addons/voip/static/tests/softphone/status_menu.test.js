import { waitNotifications } from "@bus/../tests/bus_test_helpers";

import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";

import { describe, expect, test } from "@odoo/hoot";
import { waitUntil } from "@odoo/hoot-dom";
import { advanceTime, mockDate, tick } from "@odoo/hoot-mock";

import { ResUsers } from "@voip/../tests/mock_server/mock_models/res_users";
import { receiveInvite, setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { Voip } from "@voip/core/web/voip_service";

import { browser } from "@web/core/browser/browser";
import { getService, onRpc, patchWithCleanup, serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

function patchOdooPhoneConfig(overrides = {}) {
    const config = {
        didNumber: "+32478112233",
        didNumberFormatted: "+32 478 11 22 33",
        didNumberState: "active",
        isInternalCallingProvisioned: true,
        usesOdooProvider: true,
        mainNumber: null,
        mainNumberFormatted: null,
        missedCalls: 0,
        mode: "prod",
        outboundCallerId: "+32478112233",
        outboundCallerIdFormatted: "+32 478 11 22 33",
        outboundNumbers: [
            {
                countryId: 1,
                countryName: "Belgium",
                flagUrl: "/base/static/img/country_flags/be.png",
                formatted: "+32 478 11 22 33",
                number: "+32478112233",
            },
        ],
        sharedOutboundNumbers: [],
        pbxAddress: "localhost",
        pbxExtensionNumber: "1000",
        recordingPolicy: "disabled",
        webSocketUrl: "ws://localhost",
        voicemailCode: null,
        ...overrides,
    };
    const initStoreData = ResUsers.prototype._init_store_data;
    patchWithCleanup(ResUsers.prototype, {
        _init_store_data(store) {
            initStoreData.call(this, store);
            store.add_global_values({ voipConfig: { ...config } });
        },
    });
    patchWithCleanup(Voip.prototype, {
        get areCredentialsSet() {
            return true;
        },
    });
    onRpc("get_current_voip_config", () => ({ voipConfig: { ...config }, settings: false }));
}

async function openStatusMenu() {
    await click(".o_menu_systray button[title='Show Softphone']");
    await click(".o-voip-StatusMenu-badge");
}

test("My numbers displays titled extension and personal number rows", async () => {
    patchOdooPhoneConfig();
    patchWithCleanup(browser.navigator.clipboard, {
        async writeText(text) {
            expect.step(`copied: ${text}`);
        },
    });
    await start();
    await openStatusMenu();
    await contains(".o-voip-StatusMenu-myNumbers .oi", { text: "dialpad" });
    expect(".o-voip-StatusMenu-myNumbers").toHaveText(/My numbers/);
    await click(".o-voip-StatusMenu-myNumbers");

    await contains(".o-voip-StatusMenu-number", { count: 2 });
    await contains(".text-muted", { text: "Your extension" });
    await contains(".text-muted", { text: "Your number" });
    await contains(".o-voip-StatusMenu-number:contains('1000') .o-voip-StatusMenu-numberValue", {
        text: "1000",
    });
    await contains(
        ".o-voip-StatusMenu-number:contains('+32 478 11 22 33') .o-voip-StatusMenu-numberValue",
        {
            text: "+32 478 11 22 33",
        }
    );
    await contains(".o-voip-StatusMenu-number:contains('+32 478 11 22 33') .badge.text-bg-info", {
        text: "Your caller ID",
    });
    await click(".o-voip-StatusMenu-number:contains(+32 478 11 22 33) .o-voip-StatusMenu-copy");
    expect.verifySteps(["copied: +32478112233"]);
    await click(".o-voip-StatusMenu-number:contains(1000) .o-voip-StatusMenu-copy");
    expect.verifySteps(["copied: 1000"]);
});

test("My numbers titles the default outgoing number with the active company name", async () => {
    patchOdooPhoneConfig({
        didNumber: null,
        didNumberFormatted: null,
        didNumberState: null,
        mainNumber: "+32478112233",
        mainNumberFormatted: "+32 478 11 22 33",
        outboundNumbers: [],
    });
    await start();
    await openStatusMenu();
    await click(".o-voip-StatusMenu-myNumbers");

    await contains(".o-voip-StatusMenu-number", { count: 2 });
    await contains(".text-muted", { text: "Hermit's default outgoing number" });
    await contains(
        ".o-voip-StatusMenu-number:contains('+32 478 11 22 33') .o-voip-StatusMenu-numberValue",
        { text: "+32 478 11 22 33" }
    );
    await contains(".o-voip-StatusMenu-number:contains('+32 478 11 22 33') .badge.text-bg-info", {
        text: "Your caller ID",
    });
});

test("My numbers hides the default outgoing number when a DID is available", async () => {
    patchOdooPhoneConfig({
        mainNumber: "+32478112233",
        mainNumberFormatted: "+32 478 11 22 33",
    });
    await start();
    await openStatusMenu();
    await click(".o-voip-StatusMenu-myNumbers");

    await contains(".o-voip-StatusMenu-number", { count: 2 });
    await contains(".text-muted", { text: "Your number" });
    await contains(".text-muted", {
        text: "Hermit's default outgoing number",
        count: 0,
    });
    await contains(".badge.text-bg-info", { count: 1, text: "Your caller ID" });
    await contains(".o-voip-StatusMenu-number:contains('+32 478 11 22 33') .badge.text-bg-info");
});

test("My numbers displays only the extension without any number", async () => {
    patchOdooPhoneConfig({
        didNumber: null,
        didNumberFormatted: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
        outboundNumbers: [],
    });
    await start();
    await openStatusMenu();
    await click(".o-voip-StatusMenu-myNumbers");

    await contains(".o-voip-StatusMenu-number", { count: 1 });
    await contains(".o-voip-StatusMenu-numberValue", { text: "1000" });
});

test("a pending personal number is not selectable", async () => {
    patchOdooPhoneConfig({
        didNumberState: "pending",
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
        outboundNumbers: [],
    });
    await start();
    await openStatusMenu();
    await click(".o-voip-StatusMenu-myNumbers");

    await contains(".text-muted", { text: "Your number", count: 0 });
    await contains(".badge.text-bg-info", { count: 0 });
});

test("suspended personal numbers are not selectable", async () => {
    patchOdooPhoneConfig({ didNumberState: "suspended", outboundNumbers: [] });
    await start();
    await openStatusMenu();
    await click(".o-voip-StatusMenu-myNumbers");

    await contains(".text-muted", { text: "Your number", count: 0 });
});

test("selecting one of multiple DIDs moves the caller ID badge and persists the choice", async () => {
    patchOdooPhoneConfig({
        outboundNumbers: [
            {
                countryId: 1,
                countryName: "Belgium",
                flagUrl: "/base/static/img/country_flags/be.png",
                formatted: "+32 478 11 22 33",
                number: "+32478112233",
            },
            {
                countryId: 2,
                countryName: "France",
                flagUrl: "/base/static/img/country_flags/fr.png",
                formatted: "+33 1 22 33 44 55",
                number: "+33122334455",
            },
        ],
    });
    await start();
    await openStatusMenu();
    await click(".o-voip-StatusMenu-myNumbers");

    await contains(".d-flex:has(> .text-muted:contains('Your numbers')) .form-switch");
    await contains(".o-voip-StatusMenu-number:contains('+32 478 11 22 33') .badge", {
        text: "Your caller ID",
    });
    await click(".o-voip-StatusMenu-number:contains('+33 1 22 33 44 55') > button.flex-grow-1");
    await contains(".o-voip-StatusMenu-number:contains('+33 1 22 33 44 55') .badge", {
        text: "Your caller ID",
    });
    await contains(".o-voip-StatusMenu-number:contains('+32 478 11 22 33') .badge", { count: 0 });
    expect(getService("voip").fallbackCallerId).toBe("+33122334455");
});

test("Buy a number is first for admins without a personal number", async () => {
    patchOdooPhoneConfig({
        didNumber: null,
        didNumberFormatted: null,
        didNumberState: null,
        mainNumber: "+32478112233",
        mainNumberFormatted: "+32 478 11 22 33",
    });
    onRpc("has_group", ({ args }) => args[1] === "voip.group_voip_admin");
    await start();
    patchWithCleanup(getService("action"), { doAction: (action) => expect.step(action) });
    await openStatusMenu();
    await contains(".dropdown-menu .dropdown-item:first-child .oi", {
        text: "add_shopping_cart",
    });
    expect(".dropdown-menu .dropdown-item:first-child").toHaveText(/Buy a number/);
    await click(".dropdown-menu .dropdown-item:first-child");
    expect.verifySteps(["voip.action_voip_did_number_search_wizard"]);
});

test("Buy a number is hidden from admins who already have a personal number", async () => {
    patchOdooPhoneConfig();
    onRpc("has_group", ({ args }) => args[1] === "voip.group_voip_admin");
    await start();
    await openStatusMenu();
    await contains(".dropdown-menu .dropdown-item .oi", {
        text: "add_shopping_cart",
        count: 0,
    });
});

test("non-admins without a number can request one", async () => {
    patchOdooPhoneConfig({
        didNumber: null,
        didNumberFormatted: null,
        didNumberState: null,
    });
    onRpc("has_group", () => false);
    await start();
    patchWithCleanup(getService("action"), { doAction: (action) => expect.step(action) });
    await openStatusMenu();
    await contains(".dropdown-menu .dropdown-item .oi", {
        text: "add_shopping_cart",
        count: 0,
    });
    await contains(".o-voip-StatusMenu-requestNumber");
    expect(".o-voip-StatusMenu-requestNumber").toHaveText(/Request a number/);
    await click(".o-voip-StatusMenu-requestNumber");
    expect.verifySteps(["voip.voip_phone_number_request_action"]);
});

test("Request a number is hidden from non-admins who already have a personal number", async () => {
    patchOdooPhoneConfig();
    onRpc("has_group", () => false);
    await start();
    await openStatusMenu();
    await contains(".o-voip-StatusMenu-requestNumber", { count: 0 });
});

test("indefinite DND can be turned off directly", async () => {
    mockDate("2025-01-01 01:00:00", +0);
    patchOdooPhoneConfig();
    await start();
    await openStatusMenu();
    await click("p", { text: "Do Not Disturb" });
    await contains("span", { text: "Until I turn it off" });
    await click("span", { text: "Until I turn it off" });
    await waitNotifications(["mail.record/insert"]);

    await contains(".o-voip-StatusMenu-badge", { text: "Do Not Disturb" });
    await click(".o-voip-StatusMenu-badge");
    await contains(".dropdown-item", { text: "Turn off Do Not Disturb" });
    await contains(".dropdown-item:contains('Turn off Do Not Disturb') .oi.text-success", {
        text: "phone",
    });
    await contains(".dropdown-item", { text: "Active until", count: 0 });
    await click(".dropdown-item", { text: "Turn off Do Not Disturb" });
    await waitNotifications(["mail.record/insert"]);
    await contains(".o-voip-StatusMenu-badge", { text: "Available" });
});

test("timed DND shows its expiry in the turn-off action", async () => {
    mockDate("2025-01-01 01:00:00", +0);
    patchOdooPhoneConfig();
    await start();
    getService("mail.store").self_user.res_users_settings_id.do_not_disturb_until_dt =
        luxon.DateTime.now().plus({ minutes: 15 });
    await openStatusMenu();
    await contains(".dropdown-item", { text: "Turn off Do Not Disturb" });
    await contains(".dropdown-item.align-items-start .oi.text-success.mt-1", { text: "phone" });
    const turnOffAction = document
        .querySelector(".dropdown-item .oi.text-success")
        ?.closest(".dropdown-item");
    expect(turnOffAction?.querySelector(".text-muted")?.textContent).toMatch(/^Active until /);
});

test("queue membership updates the headset indicator immediately", async () => {
    patchOdooPhoneConfig();
    const membership = { id: 42, is_logged: false, queue_name: "Support" };
    onRpc("voip.queue.agent", "get_current_user_queue_memberships", () => [membership]);
    onRpc("voip.queue.agent", "set_current_user_queue_membership", ({ args }) => {
        membership.is_logged = args[1];
        return membership.is_logged;
    });
    await start();
    await openStatusMenu();
    await click(".o-voip-StatusMenu-queues");
    await click("button", { text: "Join" });

    await contains(
        "[role='img'][aria-label='You are currently in a queue.'][title='You are currently in a queue.']"
    );
    await contains("button", { text: "Leave" });
});

test("queue memberships refresh whenever the status menu opens", async () => {
    patchOdooPhoneConfig();
    let memberships = [];
    onRpc("voip.queue.agent", "get_current_user_queue_memberships", () => memberships);
    await start();

    memberships = [{ id: 42, is_logged: false, queue_name: "Support" }];
    await openStatusMenu();
    await contains(".o-voip-StatusMenu-queues");

    await click(".o-voip-StatusMenu-badge");
    memberships = [];
    await click(".o-voip-StatusMenu-badge");
    await contains(".o-voip-StatusMenu-queues", { count: 0 });
});

test("failed queue refresh keeps the previous memberships", async () => {
    patchOdooPhoneConfig();
    let lookupFails = false;
    onRpc("voip.queue.agent", "get_current_user_queue_memberships", () => {
        if (lookupFails) {
            throw new Error("PBX unavailable");
        }
        return [{ id: 42, is_logged: false, queue_name: "Support" }];
    });
    await start();
    await openStatusMenu();
    await contains(".o-voip-StatusMenu-queues");

    await click(".o-voip-StatusMenu-badge");
    lookupFails = true;
    await click(".o-voip-StatusMenu-badge");

    await contains(".o_notification", { text: "Could not refresh your queue memberships." });
    await contains(".o-voip-StatusMenu-queues");
});

test("failed queue membership change keeps the current state actionable", async () => {
    patchOdooPhoneConfig();
    onRpc("voip.queue.agent", "get_current_user_queue_memberships", () => [
        { id: 42, is_logged: false, queue_name: "Support" },
    ]);
    onRpc("voip.queue.agent", "set_current_user_queue_membership", () => {
        throw new Error("PBX unavailable");
    });
    await start();
    await openStatusMenu();
    await click(".o-voip-StatusMenu-queues");
    await click("button", { text: "Join" });

    await contains(".o_notification", { text: "Could not update your queue membership." });
    await contains("button:not(:disabled)", { text: "Join" });
    await contains("[title='You are currently in a queue.']", { count: 0 });
});

test("failed queue membership lookup does not prevent the softphone from opening", async () => {
    patchOdooPhoneConfig();
    onRpc("voip.queue.agent", "get_current_user_queue_memberships", () => {
        throw new Error("PBX unavailable");
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");

    await contains(".o-voip-Softphone");
    await contains(".o-voip-StatusMenu-badge", { text: "Available" });
});

test("Odoo Phone audio settings reuse input and output DeviceSelect controls", async () => {
    patchOdooPhoneConfig();
    await start();
    await openStatusMenu();
    await click(".o-voip-StatusMenu-audioSettings");

    await contains(".o-mail-DeviceSelect-button[data-kind='audioinput']");
    await contains(".o-mail-DeviceSelect-button[data-kind='audiooutput']", { count: 2 });
    await contains(".o-mail-DeviceSelect-button", { text: "Click to Enable", count: 3 });
});

test("in-call status menu contains available settings and allows leaving a queue", async () => {
    patchOdooPhoneConfig({
        buyCreditsUrl: "https://example.com/credits",
        didNumber: null,
        didNumberFormatted: null,
        didNumberState: null,
    });
    onRpc("has_group", ({ args }) => args[1] === "voip.group_voip_admin");
    let isLogged = false;
    onRpc("voip.queue.agent", "get_current_user_queue_memberships", () => [
        { id: 42, is_logged: isLogged, queue_id: 7, queue_name: "Support" },
    ]);
    onRpc("voip.queue.agent", "set_current_user_queue_membership", ({ args }) => {
        expect.step(`set queue membership: ${args}`);
        isLogged = args[1];
        return isLogged;
    });
    await start();
    await openStatusMenu();
    await contains(".o-voip-StatusMenu-buyNumber");
    await contains(".o-voip-StatusMenu-myNumbers");
    await contains(".o-voip-StatusMenu-buyCredits");
    await contains(".o-voip-StatusMenu-queues");

    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-status-menu" });
    await contains(".o-voip-CallInvitation");
    await contains(".o-voip-StatusMenu-buyNumber", { count: 0 });
    await click(".o-voip-CallInvitation button:has([data-icon='phone'])");
    await contains(".o-voip-InCallView");
    isLogged = true;
    await click(".o-voip-StatusMenu-callStatus");

    await contains(".o-voip-StatusMenu-audioSettings");
    await contains(".o-voip-StatusMenu-dnd");
    await contains(".o-voip-StatusMenu-myNumbers");
    await contains(".o-voip-StatusMenu-queues");
    await contains(".o-voip-StatusMenu-buyNumber", { count: 0 });
    await contains(".o-voip-StatusMenu-buyCredits", { count: 0 });

    await click(".o-voip-StatusMenu-queues");
    await click(".o-voip-StatusMenu-queueToggle.btn-secondary");
    expect.verifySteps(["set queue membership: 42,false"]);
    await contains(".o-voip-StatusMenu-queueToggle.btn-primary");
    await contains(".o-voip-InCallView");

    await click(".o-voip-StatusMenu-queues");
    await click(".o-voip-StatusMenu-audioSettings");
    await advanceTime(1000);
    await contains(".o-mail-DeviceSelect-button[data-kind='audioinput']");
    await contains(".o-mail-DeviceSelect-button[data-kind='audiooutput']", { count: 2 });
});

test("in-call status toggle shows microphone errors unless the call is on hold", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-microphone-error" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button:has([data-icon='phone'])");
    await contains(".o-voip-InCallView");

    const voip = getService("voip");
    await voip.userAgent._audioManagerProm;
    await waitUntil(() => Boolean(voip.store.rtc.microphonePermission));
    await tick();
    const microphoneError = voip.microphoneError;
    expect(Boolean(microphoneError)).toBe(true);

    await contains(".o-voip-StatusMenu-callStatus > .oi[data-icon='error'].oi-filled.text-danger");
    expect(".o-voip-StatusMenu-callStatus").toHaveAttribute("title", microphoneError);

    await click(".o-voip-InCallView-pad button:has([data-icon='pause'])");
    await contains(".o-voip-StatusMenu-callStatus > .oi[data-icon='pause'].text-warning");
    await contains(".o-voip-StatusMenu-callStatus > .oi[data-icon='error']", { count: 0 });

    await click(".o-voip-InCallView-pad button:has([data-icon='pause'])");
    await contains(".o-voip-StatusMenu-callStatus > .oi[data-icon='error'].oi-filled.text-danger");
});

test("Demo Mode uses the status menu with DND and audio settings", async () => {
    patchOdooPhoneConfig({ usesOdooProvider: false, mode: "demo" });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-StatusMenu-badge", { text: "Demo Mode" });
    await click(".o-voip-StatusMenu-badge");
    await contains(".dropdown-menu p", { text: "Do Not Disturb" });
    await contains(".dropdown-menu .oi.text-danger", { text: "phone_disabled" });
    await contains(".dropdown-menu .dropdown-item", { text: "Available", count: 0 });
    await click(".o-voip-StatusMenu-audioSettings");
    await contains(".o-mail-DeviceSelect-button[data-kind='audioinput']");
    await contains(".o-mail-DeviceSelect-button[data-kind='audiooutput']", { count: 2 });
});

test("Demo Mode replaces the DND action with a single turn-off action", async () => {
    patchOdooPhoneConfig({ usesOdooProvider: false, mode: "demo" });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-StatusMenu-badge", { text: "Demo Mode" });
    await click(".o-voip-StatusMenu-badge");
    await click("p", { text: "Do Not Disturb" });
    await click("span", { text: "Until I turn it off" });
    await waitNotifications(["mail.record/insert"]);
    await click(".o-voip-StatusMenu-badge");

    await contains(".dropdown-item", { text: "Available", count: 0 });
    await contains(".dropdown-item", { text: "Do Not Disturb", count: 0 });
    await contains(".dropdown-item", {
        text: "Turn off Do Not Disturb",
        count: 1,
    });
});

test("Manage Providers is not offered in Demo Mode", async () => {
    patchOdooPhoneConfig({ usesOdooProvider: false, mode: "demo" });
    onRpc("has_group", ({ args }) => args[1] === "voip.group_voip_admin");
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-StatusMenu-badge", { text: "Demo Mode" });
    await click(".o-voip-StatusMenu-badge");
    await contains(".dropdown-menu .dropdown-item", { text: "Manage Providers", count: 0 });
});

test("No number reads 'Internal calls only' when internal calling is provisioned", async () => {
    patchOdooPhoneConfig({
        didNumber: null,
        didNumberFormatted: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-StatusMenu-badge", { text: "Internal calls only" });
});

test("No number without an internal calling identity keeps the 'No number' label", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-StatusMenu-badge", { text: "No number" });
});

test("external production keeps DND and exposes audio settings in the status menu", async () => {
    const pyEnv = await startServer();
    const providerId = pyEnv["voip.provider"].create({ mode: "prod" });
    pyEnv["res.users"].write([serverState.userId], { voip_provider_id: providerId });
    onRpc("get_current_voip_config", () => ({
        voipConfig: {
            didNumber: null,
            didNumberState: null,
            isInternalCallingProvisioned: false,
            usesOdooProvider: false,
            missedCalls: 0,
            mode: "prod",
            outboundCallerId: null,
            outboundNumbers: [],
            pbxAddress: "localhost",
            pbxExtensionNumber: null,
            recordingPolicy: "disabled",
            sharedOutboundNumbers: [],
            webSocketUrl: "ws://localhost",
            voicemailCode: null,
        },
        settings: false,
    }));
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");

    await contains(".o-voip-StatusMenu-badge", { text: "Available" });
    await contains("header button[title='Audio settings']", { count: 0 });
    await click(".o-voip-StatusMenu-badge");
    await contains(".o-voip-StatusMenu-audioSettings");
    await contains(".dropdown-menu .dropdown-item .oi", {
        text: "add_shopping_cart",
        count: 0,
    });
    await contains(".dropdown-menu .dropdown-item", { text: "Available", count: 0 });
    await contains(".o-voip-StatusMenu-myNumbers", { count: 0 });
    await contains(".o-voip-StatusMenu-queues", { count: 0 });
    await click(".o-voip-StatusMenu-audioSettings");
    await contains(".o-mail-DeviceSelect-button[data-kind='audioinput']");
    await contains(".o-mail-DeviceSelect-button[data-kind='audiooutput']", { count: 2 });
    await click(".dropdown-menu p", { text: "Do Not Disturb" });
    await contains("span", { text: "Until I turn it off" });
});

test("a microphone error guides the user through the status badge to audio settings", async () => {
    patchOdooPhoneConfig();
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    const voip = getService("voip");
    await voip.userAgent._audioManagerProm;
    await waitUntil(() => Boolean(voip.store.rtc.microphonePermission));
    await tick();
    voip.microphoneError = "Microphone access is required.";

    await contains("header .o-voip-customMicIcon", { count: 0 });
    await contains(".o-voip-StatusMenu-badge[title='Microphone access is required.']");
    await contains(".o-voip-StatusMenu-badge > .oi.text-danger", { text: "error" });
    await click(".o-voip-StatusMenu-badge");
    await contains(".o-voip-StatusMenu-audioSettings .oi.text-danger", { text: "error" });
    await contains(".o-voip-StatusMenu-enableAudio", { count: 0 });
});
