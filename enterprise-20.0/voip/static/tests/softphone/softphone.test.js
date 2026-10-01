import { waitNotifications } from "@bus/../tests/bus_test_helpers";

import {
    click,
    contains,
    insertText,
    mockPipWindow,
    start,
    startServer,
    triggerHotkey,
} from "@mail/../tests/mail_test_helpers";
import { after, animationFrame, describe, expect, test } from "@odoo/hoot";
import { edit, waitUntil } from "@odoo/hoot-dom";
import { advanceTime, tick } from "@odoo/hoot-mock";
import { ResUsers } from "@voip/../tests/mock_server/mock_models/res_users";
import { receiveInvite, setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { Ringtone } from "@voip/core/web/ringtone";
import { Voip } from "@voip/core/web/voip_service";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { getService, onRpc, serverState } from "@web/../tests/web_test_helpers";
import { patch } from "@web/core/utils/patch";

describe.current.tags("desktop");
setupVoipTests();

function getZIndex(el) {
    return Number(getComputedStyle(el).zIndex) || 0;
}

function patchVoipConfig(overrides, credentialsSet = true) {
    const config = {
        didNumber: "+3287000099",
        didNumberState: "pending",
        isInternalCallingProvisioned: true,
        usesOdooProvider: true,
        missedCalls: 0,
        mode: "prod",
        outboundCallerId: "+3287000011",
        outboundCallerIdFormatted: "+32 87 00 00 11",
        outboundNumbers: [],
        pbxExtensionNumber: "1000",
        pbxAddress: "localhost",
        recordingPolicy: "disabled",
        sharedOutboundNumbers: [],
        webSocketUrl: "ws://localhost",
        voicemailCode: null,
        ...overrides,
    };
    const initStoreData = ResUsers.prototype._init_store_data;
    patch(ResUsers.prototype, {
        _init_store_data(store) {
            initStoreData.call(this, store);
            store.add_global_values({ voipConfig: { ...config } });
        },
    });
    patch(Voip.prototype, {
        get areCredentialsSet() {
            return credentialsSet;
        },
    });
    // Serve the same patched config if opening the softphone refreshes it.
    onRpc("get_current_voip_config", () => ({ voipConfig: { ...config }, settings: false }));
}

async function clearMicrophoneError() {
    const voip = getService("voip");
    await voip.userAgent._audioManagerProm;
    await waitUntil(() => Boolean(voip.store.rtc.microphonePermission));
    await tick();
    voip.microphoneError = null;
}

function mockMediaSession({ unsupported = false } = {}) {
    let handler;
    patch(navigator.mediaSession, {
        setActionHandler(action, callback) {
            if (unsupported) {
                throw new DOMException("Unsupported action", "NotSupportedError");
            }
            expect(action).toBe("enterpictureinpicture");
            handler = callback;
        },
    });
    return {
        get handler() {
            return handler;
        },
    };
}

test("Clicking on close button closes the softphone.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-Softphone");
    await click(".o-voip-Softphone button[title='Hide']");
    await contains(".o-voip-Softphone", { count: 0 });
});

test("production calls open PiP automatically on content occlusion", async () => {
    patchVoipConfig({ didNumberState: "active", outboundCallerId: "+3287000099" });
    const mediaSession = mockMediaSession();
    await start();
    const voipPip = getService("voip.pip");
    patch(voipPip, {
        async open() {
            expect.step("open_pip");
            return {};
        },
    });

    await click(".o_menu_systray button[title='Show Softphone']");
    receiveInvite({
        phone_number: "0123456789",
        sip_call_id: "test-invite-001",
    });
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    await contains(".o-voip-Softphone header [data-icon='content_copy']", { count: 0 });

    await mediaSession.handler({ enterPictureInPictureReason: "useraction" });
    expect.verifySteps([]);
    await mediaSession.handler({ enterPictureInPictureReason: "contentoccluded" });
    expect.verifySteps(["open_pip"]);
    await contains(".o-voip-Softphone", { count: 0 });
});

test("VoIP registers PiP after an overlapping Discuss call ends", async () => {
    patchVoipConfig({ didNumberState: "active", outboundCallerId: "+3287000099" });
    const mediaSession = mockMediaSession();
    await start();
    const voip = getService("voip");
    const discussSession = voip.store["discuss.channel.rtc.session"].insert({ id: 1 });
    voip.store.rtc.localSession = discussSession;
    await tick();
    const voipPip = getService("voip.pip");
    patch(voipPip, {
        async open() {
            expect.step("open_pip");
            return {};
        },
    });

    await click(".o_menu_systray button[title='Show Softphone']");
    receiveInvite({ phone_number: "0123456789", sip_call_id: "test-invite-001" });
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    expect(mediaSession.handler).toBe(undefined);

    voip.store.rtc.localSession = null;
    await tick();

    expect(mediaSession.handler).toBeInstanceOf(Function);
    await mediaSession.handler({ enterPictureInPictureReason: "contentoccluded" });
    expect.verifySteps(["open_pip"]);
});

test("demo calls support PiP without copying the web app manifest", async () => {
    patch(window, {
        open() {
            return document.createElement("iframe").contentWindow;
        },
    });
    const mediaSession = mockMediaSession();
    const { popoutIframe, popoutWindow } = mockPipWindow();
    const manifest = document.createElement("link");
    manifest.rel = "manifest";
    manifest.href = "/web/manifest.webmanifest";
    document.head.append(manifest);
    after(() => manifest.remove());
    await start();
    const voipPip = getService("voip.pip");
    patch(voipPip, {
        get isSupported() {
            return true;
        },
    });
    await click(".o_menu_systray button[title='Show Softphone']");
    receiveInvite({ phone_number: "0123456789", sip_call_id: "test-invite-001" });
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    expect(mediaSession.handler).toBeInstanceOf(Function);
    await mediaSession.handler({ enterPictureInPictureReason: "contentoccluded" });
    await contains(".o-voip-PipWindow", { target: popoutIframe.contentDocument });
    expect(popoutIframe.contentDocument.querySelector('link[rel~="manifest"]')).toBe(null);
    await contains(".o-voip-Softphone", { count: 0 });
    await click(".o_menu_systray button[title='Show Softphone']");
    expect(popoutWindow.closed).toBe(true);
    await contains(".o-voip-Softphone");
});

test("unsupported MediaSession PiP registration is a silent no-op", async () => {
    patchVoipConfig({ didNumberState: "active", outboundCallerId: "+3287000099" });
    const mediaSession = mockMediaSession({ unsupported: true });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    receiveInvite({
        phone_number: "0123456789",
        sip_call_id: "test-invite-001",
    });
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    expect(mediaSession.handler).toBe(undefined);
    await contains(".o-voip-Softphone header [data-icon='content_copy']", { count: 0 });
});

test("ending a call clears the MediaSession PiP handler", async () => {
    patchVoipConfig({ didNumberState: "active", outboundCallerId: "+3287000099" });
    const mediaSession = mockMediaSession();
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    receiveInvite({
        phone_number: "0123456789",
        sip_call_id: "test-invite-001",
    });
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    expect(mediaSession.handler).toBeInstanceOf(Function);

    await click(".o-voip-InCallView button[title='Hang up']");
    await contains(".o-voip-InCallView", { count: 0 });
    expect(mediaSession.handler).toBe(null);
});

test("The Escape key closes the softphone.", async () => {
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await contains(".o-voip-Softphone");
    await triggerHotkey("Escape");
    await contains(".o-voip-Softphone", { count: 0 });
});

test("A later modal stacks above an already opened softphone dropdown", async () => {
    function isStackedAbove(upEl, downEl) {
        const upperZIndex = getZIndex(upEl);
        const lowerZIndex = getZIndex(downEl);
        if (upperZIndex !== lowerZIndex) {
            return upperZIndex > lowerZIndex;
        }
        return Boolean(downEl.compareDocumentPosition(upEl) & Node.DOCUMENT_POSITION_FOLLOWING);
    }

    const pyEnv = await startServer();
    const providerId = pyEnv["voip.provider"].create({ mode: "prod" });
    pyEnv["res.users"].write([serverState.userId], { voip_provider_id: providerId });
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await contains(".o-voip-Softphone");
    await click(".o-voip-StatusMenu-badge:contains(Available)");
    await contains(".o-overlay-container .dropdown-menu");
    getService("dialog").add(ConfirmationDialog, {
        body: "Test dialog",
        confirm() {},
        cancel() {},
    });
    await contains(".o-overlay-container .dropdown-menu");
    await contains(".o-overlay-container .modal");
    const dropdownOverlayItemEl = document
        .querySelector(".o-overlay-container .dropdown-menu")
        .closest(".o-overlay-item");
    const modalOverlayItemEl = document
        .querySelector(".o-overlay-container .modal")
        .closest(".o-overlay-item");
    expect(isStackedAbove(modalOverlayItemEl, dropdownOverlayItemEl)).toBe(true);
});

test("An incoming call promotes an already opened softphone above existing modals", async () => {
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await contains(".o-voip-Softphone");
    getService("dialog").add(ConfirmationDialog, {
        body: "Test dialog",
        confirm() {},
        cancel() {},
    });
    await contains(".o-overlay-container > .o-overlay-item:last-child .modal");
    receiveInvite({
        phone_number: "0123456789",
        sip_call_id: "test-invite-overlay-001",
    });

    // Check the modal is still there but the last overlay is now the softphone
    await contains(".o-overlay-container > .o-overlay-item:last-child .o-voip-Softphone");
    await contains(".o-overlay-container > .o-overlay-item:first-child .modal");

    // Also ensure that z-indexes are not messed with again
    const softphoneEl = document.querySelector(".o-overlay-container .o-voip-Softphone");
    const modalOverlayItemEl = document
        .querySelector(".o-overlay-container .modal")
        .closest(".o-overlay-item");
    const softphoneOverlayItemEl = softphoneEl.closest(".o-overlay-item");
    expect(getComputedStyle(softphoneEl).zIndex).toBe("auto");
    expect(getZIndex(softphoneOverlayItemEl)).toBe(getZIndex(modalOverlayItemEl));
});

test("When DND is enabled, an incoming call does not promote the softphone above existing modals", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({
        do_not_disturb_until_dt: luxon.DateTime.utc()
            .plus({ hour: 1 })
            .toFormat("yyyy-MM-dd HH:mm:ss"),
        user_id: serverState.userId,
    });
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await contains(".o-voip-Softphone");
    getService("dialog").add(ConfirmationDialog, {
        body: "Test dialog",
        confirm() {},
        cancel() {},
    });
    await contains(".o-overlay-container > .o-overlay-item:last-child .modal");
    receiveInvite({
        phone_number: "0123456789",
        sip_call_id: "test-invite-overlay-001",
    });
    await contains(".o-voip-CallInvitation");
    // Needed to wait for the overlay switch, otherwise this tests nothing
    await animationFrame();

    // Check the modal is still there, still the last overlay
    await contains(".o-overlay-container > .o-overlay-item:first-child .o-voip-Softphone");
    await contains(".o-overlay-container > .o-overlay-item:last-child .modal");
});

test("Active tab does not need to be tabbable.", async () => {
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await contains(".o-voip-Softphone-navItem", { count: 3 });
    expect(".o-voip-Softphone-navItem:not(.active)").not.toHaveAttribute("tabindex");
    expect(".o-voip-Softphone-navItem.active").toHaveAttribute("tabindex", "-1");
});

test("Make sure the softphone is considered the active element of the UI when opened", async () => {
    await start();
    const ui = getService("ui");

    function expectSoftphoneAsUIActiveElement(shouldBeActive) {
        expect(Boolean(ui.activeElement?.closest?.(".o-voip-Softphone"))).toBe(shouldBeActive);
    }
    async function toggleSoftphone() {
        return click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    }

    expectSoftphoneAsUIActiveElement(false);
    await toggleSoftphone();
    await contains(".o-voip-Softphone");
    expectSoftphoneAsUIActiveElement(true);
    await toggleSoftphone();
    await contains(".o-voip-Softphone", { count: 0 });
    expectSoftphoneAsUIActiveElement(false);
});

test("Softphone dropdown closes when clicking outside the softphone", async () => {
    const pyEnv = await startServer();
    const providerId = pyEnv["voip.provider"].create({ mode: "prod" });
    pyEnv["res.users"].write([serverState.userId], { voip_provider_id: providerId });
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await contains(".o-voip-Softphone");

    await click(".o-voip-StatusMenu-badge:contains(Available)");
    await contains(".o-overlay-container .dropdown-menu");

    await click(".o_menu_systray");
    await contains(".o-overlay-container .dropdown-menu", { count: 0 });
});

test.tags("focus required");
test("Search bar is focused after switching to a tab with search bar.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Dialer input:focus");
    await click("button[data-tab='recent']");
    await contains("input[placeholder='Search contacts…']:focus");
});

test.tags("focus required");
test("Search bar is focused after reopen the softphone.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Dialer input:focus");
    await click(".o-voip-Softphone button[title='Hide']");
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-Dialer input:focus");
    await click("button[data-tab='recent']");
    await click(".o-voip-Softphone button[title='Hide']");
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("input[placeholder='Search contacts…']:focus");
});

test.tags("focus required");
test("Search bar keeps focus after typing a letter.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    // The Recent tab search bar is focused when the softphone opens.
    await contains("input[placeholder='Search contacts…']:focus");
    // Typing a letter switches the Recent tab from the call list to the
    // contact search results, which destroys the current search input and
    // mounts a fresh one. The new input must reclaim focus so that the user
    // can keep typing.
    await insertText("input[placeholder='Search contacts…']:focus", "a");
    await contains("input[placeholder='Search contacts…']:focus");
});

test("pending search spinner is not delayed by true-to-true pending updates", async () => {
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await contains("#o-voip-Tab-searchInput");

    const voip = getService("voip");

    voip._contactRpc = Promise.resolve(); // hasPendingRequest: false -> true
    await animationFrame();

    await advanceTime(300);

    voip._contactRpc = Promise.resolve(); // hasPendingRequest: true -> true
    await animationFrame();

    await advanceTime(100);
    await animationFrame();

    expect(".o-voip-Softphone [data-icon='autorenew']").toHaveCount(1);
});

test("Opening the softphone selects the Recent tab.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("button[data-tab='recent'].active");
    await contains("button[data-tab='dialer'].active", { count: 0 });
    expect("button[data-tab]:first-child span").toHaveText("Recent");
    expect("button[data-tab]:nth-child(2) span").toHaveText("Keypad");
});

test("Clicking on a tab makes it the active tab.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains("button[data-tab='dialer'].active");
    await click("button[data-tab='recent']");
    await contains("button[data-tab='recent'].active");
});

test("Using VoIP in prod mode without configuring the server shows an error", async () => {
    const pyEnv = await startServer();
    const providerId = pyEnv["voip.provider"].create({
        mode: "prod",
        name: "Axivox super cool",
        pbx_ip: "",
        ws_server: "",
    });
    pyEnv["res.users"].write([serverState.userId], { voip_provider_id: providerId });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-ErrorScreen");
});

test("Connecting shows a centered loading state instead of an error", async () => {
    await start();
    const voipService = getService("voip");
    voipService.triggerError({ isConnecting: true, message: "Connecting…" });
    await click(".o_menu_systray button[title='Show Softphone']");

    await contains(".o-voip-ErrorScreen[role='status'] .oi-spin");
    expect(".o-voip-ErrorScreen").toHaveText("Connecting…");
    await contains(".o-voip-ErrorScreen", { text: "Something went wrong", count: 0 });
});

test.tags("focus required");
test("When a call is created, a partner with a corresponding phone number is displayed", async () => {
    const pyEnv = await startServer();
    const phoneNumber = "0456 703 6196";
    pyEnv["res.partner"].create({ name: "Maxime Randonnées", phone: phoneNumber });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    // dropdown requires an extra delay before click (because handler is registered in useEffect)
    await contains("button[data-tab='dialer']");
    await click("button[data-tab='dialer']");
    // ensure initial focusing is done before inserting text to avoid focus reset
    await contains(".o-voip-Dialer input:focus");
    await insertText(".o-voip-Dialer input:focus", phoneNumber);
    await triggerHotkey("Enter");
    await advanceTime(5000);
    await contains(".o-voip-InCallView", { text: "Maxime Randonnées" });
});

test("An incoming call from a known contact shows both the contact name and the phone number.", async () => {
    const pyEnv = await startServer();
    const phoneNumber = "+32 478 55 77 88";
    pyEnv["res.partner"].create({ name: "Emam Ashour", phone: phoneNumber });
    await start();
    receiveInvite({ phone_number: phoneNumber, sip_call_id: "test-invite-known" });
    await contains(".o-voip-CallInvitation:contains('Emam Ashour')");
    await contains(".o-voip-CallInvitation:contains('478 55 77 88')");
});

test("An incoming call from an unknown number shows the number on its own line (where the country flag lives).", async () => {
    await startServer();
    await start();
    receiveInvite({ phone_number: "+32 478 55 77 88", sip_call_id: "test-invite-unknown" });
    await contains(".o-voip-CallInvitation .o-voip-PhoneNumber:contains('478 55 77 88')");
});

test("A pending personal number uses the Default Outgoing Number under the approval header.", async () => {
    patchVoipConfig({ didNumberState: "pending" });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await clearMicrophoneError();
    await contains(".o-voip-Softphone header:contains(Number under review)");
    await contains(".o-voip-Softphone header [title*='Calls use +32 87 00 00 11']");
    await contains(".o-voip-Softphone-content > .alert", {
        text: "Calls use +32 87 00 00 11 while your number is under review.",
    });
});

test("An ordering number without login details shows a notice alongside call history.", async () => {
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        phone_number: "+32498111111",
        state: "terminated",
        user_id: serverState.userId,
    });
    patchVoipConfig({ didNumberState: "ordering" }, false);
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");

    await contains(".o-voip-ErrorScreen", { count: 0 });
    await contains(".o-voip-Softphone header", { text: "Number under review" });
    await contains(".o-voip-History .o-voip-TabEntry");
    await contains(".o-voip-Softphone-content > .alert", {
        text: "Your number has been ordered and is under review. We'll notify you when it's ready.",
    });
});

test("An active first number waits for Odoo Phone provisioning without an error.", async () => {
    patchVoipConfig(
        {
            didNumberState: "active",
            isInternalCallingProvisioned: false,
            outboundCallerId: "+3287000099",
            outboundCallerIdFormatted: "+32 87 00 00 99",
        },
        false
    );
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");

    await contains(".o-voip-ErrorScreen", { count: 0 });
    await contains(".o-voip-Softphone-content > .alert", {
        text: "Your number is active. Your phone setup is still being finalized. Calling will be available once setup is complete.",
    });
});

test("The Default Outgoing Number avoids the No-number state when no personal number is assigned.", async () => {
    patchVoipConfig({ didNumber: null, didNumberState: null });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-StatusMenu-badge", { text: "Available" });
    await contains(".o-voip-Softphone-main", { text: "Calls use +32 87 00 00 11.", count: 0 });
    await contains(".o-voip-Softphone header:contains(No number)", { count: 0 });
});

test("No number keeps internal calling available for a provisioned extension.", async () => {
    patchVoipConfig({
        didNumber: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
    });
    onRpc("voip.call", "get_recent_phone_calls", () => ({ ids: [], store_data: {} }));
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await clearMicrophoneError();
    await contains(".o-voip-Softphone header:contains(Internal calls only)");
    await contains(".o-voip-Softphone header [title*='extension 1000']");
    await contains(".o-voip-Softphone", {
        text: "Internal calls are available. External calls require an active phone number.",
    });
    await contains(".o-voip-Softphone .o_view_nocontent");
    expect(".o-voip-Softphone .o_view_nocontent").toHaveText(
        /Internal calls are available through your extension\./
    );
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Dialer button[title='Call']:not(:disabled)");
});

test("No number without a provisioned extension explains that internal calling is unavailable.", async () => {
    patchVoipConfig(
        {
            didNumber: null,
            didNumberState: null,
            outboundCallerId: null,
            outboundCallerIdFormatted: null,
            isInternalCallingProvisioned: false,
            pbxExtensionNumber: null,
        },
        false
    );
    onRpc("voip.call", "get_recent_phone_calls", () => ({ ids: [], store_data: {} }));
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-Softphone header:contains(No number)");
    await contains(".o-voip-Softphone .o_view_nocontent");
    expect(".o-voip-Softphone .o_view_nocontent").toHaveText(
        /Internal calling is not configured for this user\./
    );
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Dialer button[title='Call']:disabled");
});

test("Admins open the buy-number wizard from the No-number status menu.", async () => {
    onRpc("has_group", ({ args }) =>
        ["voip.group_voip_officer", "voip.group_voip_admin"].includes(args[1])
    );
    patchVoipConfig({
        didNumber: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
    });
    await start();
    patch(getService("action"), { doAction: (action) => expect.step(action) });
    await click(".o_menu_systray button[title='Show Softphone']");
    await click(".o-voip-StatusMenu-badge:contains(Internal calls only)");
    await click(".dropdown-menu .dropdown-item:contains(Buy a number)");
    expect.verifySteps(["voip.action_voip_did_number_search_wizard"]);
});

test("The No-number status menu does not offer number purchase to officers.", async () => {
    onRpc("has_group", ({ args }) => args[1] === "voip.group_voip_officer");
    patchVoipConfig({
        didNumber: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click(".o-voip-StatusMenu-badge:contains(Internal calls only)");
    await contains(".dropdown-menu");
    await contains(".dropdown-menu .dropdown-item:contains(Buy a number)", { count: 0 });
});

test("The No-number status menu does not offer number purchase to regular users.", async () => {
    onRpc("has_group", () => false);
    patchVoipConfig({
        didNumber: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click(".o-voip-StatusMenu-badge:contains(Internal calls only)");
    await contains(".dropdown-menu");
    await contains(".dropdown-menu .dropdown-item:contains(Buy a number)", { count: 0 });
});

test("The softphone top bar indicates 'Demo Mode' when a demo number is active.", async () => {
    patchVoipConfig({
        usesOdooProvider: false,
        mode: "demo",
        didNumber: "+3287000099",
        didNumberState: "active",
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await clearMicrophoneError();
    await contains(
        ".o-voip-Softphone header [title='Calls are simulated in Demo Mode. Switch to Odoo Phone Service to use +32 87 00 00 11.']:contains(Demo Mode)"
    );
});

test("VoIP officers can use Demo Mode without a provider.", async () => {
    onRpc("has_group", ({ args }) => args[1] === "voip.group_voip_officer");
    patchVoipConfig({
        usesOdooProvider: false,
        mode: "demo",
        didNumber: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await clearMicrophoneError();
    await contains(".o-voip-ErrorScreen", { count: 0 });
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Dialer button[title='Call']:not(:disabled)");
});

test("Demo mode shows the waiting header while a number is pending.", async () => {
    patchVoipConfig({
        usesOdooProvider: false,
        mode: "demo",
        didNumber: "+3287000099",
        didNumberState: "pending",
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await clearMicrophoneError();
    await contains(
        ".o-voip-Softphone header [title='Your number is under review. Calls remain simulated in Demo Mode.']:contains(Number under review)"
    );
});

test("Demo mode without a number shows the buy-number card.", async () => {
    onRpc("has_group", ({ args }) => args[1] === "voip.group_voip_admin");
    patchVoipConfig({
        usesOdooProvider: false,
        mode: "demo",
        didNumber: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
    });
    onRpc("voip.call", "get_recent_phone_calls", () => ({ ids: [], store_data: {} }));
    await start();
    patch(getService("action"), { doAction: (action) => expect.step(action) });
    await click(".o_menu_systray button[title='Show Softphone']");
    await clearMicrophoneError();
    await contains(
        ".o-voip-Softphone header button[title='Calls are simulated in Demo Mode. Get a number to make and receive real calls with Odoo Phone Service.']:contains(No number)"
    );
    await contains(".o-voip-Softphone .o_view_nocontent", {
        text: "Purchase a phone number to make and receive calls with Odoo Phone Service.",
    });
    await contains(".o-voip-Softphone button:contains(Buy a Number)");
    await click(".o-voip-StatusMenu-badge:contains(No number)");
    await click(".dropdown-menu .dropdown-item:contains(Buy a number)");
    expect.verifySteps(["voip.action_voip_did_number_search_wizard"]);
});

test("An external production provider does not show the Odoo buy-number card.", async () => {
    patchVoipConfig({
        usesOdooProvider: false,
        mode: "prod",
        didNumber: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
    });
    onRpc("voip.call", "get_recent_phone_calls", () => ({ ids: [], store_data: {} }));
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-Softphone .o_view_nocontent", { count: 0 });
});

test("The Demo Mode status menu does not expose provider settings.", async () => {
    onRpc("has_group", ({ args }) =>
        ["voip.group_voip_officer", "voip.group_voip_admin"].includes(args[1])
    );
    patchVoipConfig({
        usesOdooProvider: false,
        mode: "demo",
        didNumber: "+3287000099",
        didNumberState: "active",
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-StatusMenu-badge", { text: "Demo Mode" });
    await click(".o-voip-StatusMenu-badge");
    await contains(".dropdown-menu .dropdown-item", { text: "Manage Providers", count: 0 });
});

test("The Dialer's Call button stays enabled in demo mode without a number.", async () => {
    patchVoipConfig({
        usesOdooProvider: false,
        mode: "demo",
        didNumber: false,
        didNumberState: false,
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Dialer button[title='Call']:not(:disabled)");
});

test("A suspended number in demo mode stays callable under the Demo Mode header.", async () => {
    patchVoipConfig({
        usesOdooProvider: false,
        mode: "demo",
        didNumber: "+3287000099",
        didNumberState: "suspended",
        buyCreditsUrl: "https://iap.odoo.com/credit",
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-Softphone header:contains(Demo Mode)");
    await contains(".o-voip-Softphone:contains(Number suspended)", { count: 0 });
    await contains(".o-voip-ErrorScreen", { count: 0 });
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Dialer button[title='Call']:not(:disabled)");
});

test("A suspended number in production uses the Default Outgoing Number and offers credits.", async () => {
    patchVoipConfig({
        usesOdooProvider: true,
        mode: "prod",
        didNumber: "+3287000099",
        didNumberState: "suspended",
        buyCreditsUrl: "https://iap.odoo.com/credit",
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-Softphone header:contains(Suspended)");
    await contains(".o-voip-Softphone-content > .alert", {
        text: "Calls use +32 87 00 00 11 until your number is reactivated.",
    });
    await click(".o-voip-StatusMenu-badge");
    await contains(".dropdown-menu a:contains(Buy Credits)");
    expect(".o-voip-History p").toHaveText(/Your call history is empty!/);
    await contains(".o-voip-ErrorScreen", { count: 0 });
});

test("Second incoming call is shown as invitation while first call continues.", async () => {
    await start();
    const invite1 = receiveInvite({
        phone_number: "0123456789",
        sip_call_id: "test-invite-001",
    });
    expect(invite1.state).toBe(SIP.SessionState.Initial);
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    expect(invite1.state).toBe(SIP.SessionState.Established);
    await contains(".o-voip-InCallView");
    const invite2 = receiveInvite({
        phone_number: "9876543210",
        sip_call_id: "test-invite-002",
    });
    expect(invite2.state).toBe(SIP.SessionState.Initial);
    await contains(".o-voip-CallInvitation");
    const { userAgent } = getService("voip");
    expect(Object.keys(userAgent.sessions).length).toBe(2);
});

test("No crash when call is not ready", async () => {
    const def = Promise.withResolvers();
    await start();
    onRpc("get_or_create", async () => {
        await def.promise;
    });

    const invite = {
        phone_number: "0123456789",
        sip_call_id: "test-invite-001",
    };
    receiveInvite(invite);
    await contains(".o-voip-CallInvitation");
    await contains(".o-voip-ActionButton[title='Create']");

    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    await contains(".o-voip-ActionButton[title='Create']");

    await click(".o-voip-InCallView button[title='Hang up']");
    await click("button[data-tab='recent']");
    await contains(".o-voip-TabEntry", { count: 0 });

    def.resolve();
    await contains(".o-voip-TabEntry", { count: 1 });
    expect(".o-voip-TabEntry:last span:first").toHaveText("0123456789");
    expect(".o-voip-TabEntry:last span:eq(1)").toHaveText(/Incoming call/);
});

test("Create a contact when call is not ready", async () => {
    const def = Promise.withResolvers();
    await start();
    onRpc("get_or_create", async () => {
        await def.promise;
    });

    const invite = {
        phone_number: "0123456789",
        sip_call_id: "test-invite-001",
    };
    receiveInvite(invite);
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");

    await click(".o-voip-ActionButton[title='Create']");
    await click(".o_popover .o-dropdown-item:contains('Contact')");
    await click(".o_form_view .o_field_char[name='name']");
    await edit("Caller name");
    await click(".o_form_button_save");

    await click(".o-voip-InCallView button[title='Hang up']");
    await click("button[data-tab='recent']");
    await contains(".o-voip-TabEntry", { count: 0 });

    def.resolve();
    await contains(".o-voip-TabEntry", { count: 1 });
    expect(".o-voip-TabEntry:last span:first").toHaveText("Caller name");
    expect(".o-voip-TabEntry:last span:eq(1)").toHaveText(/Incoming call/);
});

test("When DND is enabled, incoming calls should be accepted without toggling the softphone or playing a ringtone", async () => {
    patch(Ringtone.prototype, {
        play() {
            expect.step("play");
        },
    });
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({
        do_not_disturb_until_dt: luxon.DateTime.utc()
            .plus({ hour: 1 })
            .toFormat("yyyy-MM-dd HH:mm:ss"),
        user_id: serverState.userId,
    });
    await start();
    const invite1 = {
        phone_number: "0123456789",
        sip_call_id: "test-invite-001",
    };

    expect(".o-voip-Softphone").toHaveCount(0);

    receiveInvite(invite1);
    await contains(".o_nav_entry.text-success:has(i.oi[data-icon='phone'].oi-filled)");
    expect(".o-voip-Softphone").toHaveCount(0);

    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-CallInvitation");

    await click(".o-voip-CallInvitation button[title='Reject the call']");
    await contains(".o-voip-CallInvitation", { count: 0 });

    expect(".o-voip-Softphone").toHaveCount(1);

    const invite2 = {
        phone_number: "0123456789",
        sip_call_id: "test-invite-002",
    };

    receiveInvite(invite2);
    await contains(".o_nav_entry.text-success:has(i.oi[data-icon='phone'].oi-filled)");
    await contains(".o-voip-CallInvitation");

    await click(".o-voip-CallInvitation button[title='Reject the call']");
    await contains(".o-voip-CallInvitation", { count: 0 });

    expect.verifySteps([]);
});

test("changing DND while an incoming call is ringing updates the ringtone", async () => {
    patch(Ringtone.prototype, {
        play(ringtone) {
            this.playingRingtone = ringtone;
        },
        stop() {
            this.playingRingtone = undefined;
        },
    });
    await start();
    const voip = getService("voip");
    receiveInvite({
        phone_number: "0123456789",
        sip_call_id: "test-invite-dnd-ringtone",
    });
    const session = voip.userAgent.callInvitationSession;
    session.ringleader = true;
    voip.userAgent.requestIncomingRingtone();
    expect(session.ringtone.playingRingtone).toBe("incoming");

    const settings = voip.store.self_user.res_users_settings_id;
    settings.setVoipDoNotDisturb(-1);
    await waitNotifications(["mail.record/insert"]);
    expect(session.ringtone.playingRingtone).toBe(undefined);

    settings.setVoipDoNotDisturb(0);
    await waitNotifications(["mail.record/insert"]);
    expect(session.ringtone.playingRingtone).toBe("incoming");
});

test("end_call reaches the server before start_call", async () => {
    const startCallDef = Promise.withResolvers();
    await start();
    onRpc("start_call", async () => {
        await startCallDef.promise;
    });

    receiveInvite({
        phone_number: "0123456789",
        sip_call_id: "test-invite-001",
    });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");

    await advanceTime(5000);

    // Hang up while start_call is still blocked; end_call should proceed independently.
    await click(".o-voip-InCallView button[title='Hang up']");
    await click("button[data-tab='recent']");
    await contains(".o-voip-TabEntry", { count: 1 });
    expect(".o-voip-TabEntry:last span:first").toHaveText("0123456789");

    // Resolving start_call should not cause errors or duplicate entries.
    startCallDef.resolve();
    await contains(".o-voip-TabEntry", { count: 1 });
    await contains(".o-voip-TabEntry:last span:eq(1):contains(/Incoming call.*[4-6]s/)", {
        count: 1,
    });
});

test("prefill phone from active form", async () => {
    await start();
    const action = getService("action");
    patch(action, {
        currentController: {
            props: { type: "form", resModel: "res.partner" },
            currentState: { resId: 42 },
        },
    });
    onRpc("voip.call", "get_prefill_data", () => ({
        partner_id: 99,
        phone: "+1 234 567 8900",
        store_data: {
            "res.partner": [
                {
                    id: 99,
                    name: "Test Partner",
                    complete_name: "Test Partner",
                    phone: "+1 (234) 567-8900",
                },
            ],
        },
    }));

    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("button[data-tab='dialer'].active");
    await contains(".o-voip-Keypad-input:value('+1 234 567 8900')");
    await contains("button[data-tooltip='Test Partner']");
});

test("automatic formatting preserves prefill but selecting a country invalidates it", async () => {
    onRpc("voip.call", "get_prefill_data", () => ({
        partner_id: 99,
        phone: "+12345678900",
        store_data: {},
    }));
    onRpc("/voip/parse_phone_number", () => ({
        countryId: 1,
        isValid: true,
        phone_number: "+1 234 567 8900",
        storeData: {
            "res.country": {
                id: 1,
                name: "United States",
                code: "US",
                phone_code: "1",
            },
        },
    }));
    onRpc("/voip/update_country_code", () => ({
        isValid: true,
        phone_number: "+1 234 567 8900",
    }));

    await start();
    const voip = getService("voip");
    patch(voip.action, {
        currentController: {
            props: { type: "form", resModel: "res.partner" },
            currentState: { resId: 42 },
        },
    });
    await click(".o_menu_systray button:has(> [data-icon='phone'])");
    await contains(".o-voip-Keypad-input:value('+1 234 567 8900')");
    expect(voip.softphone.dialer.prefillContext).toEqual({
        resModel: "res.partner",
        resId: 42,
        partnerId: 99,
    });

    await click(".o-voip-Keypad-searchBar .o-voip-countryFlag");
    await click(".o-voip-countryDropdown .dropdown-item");
    await waitUntil(() => voip.softphone.dialer.prefillContext === null);
});

test("reopening the softphone restores the prefilled phone country", async () => {
    onRpc("voip.call", "get_prefill_data", () => ({
        partner_id: 99,
        phone: "+12345678900",
        store_data: {},
    }));
    onRpc("/voip/parse_phone_number", () => ({
        countryId: 2,
        isValid: true,
        phone_number: "+1 234 567 8900",
        storeData: {
            "res.country": {
                id: 2,
                name: "United States",
                code: "US",
                phone_code: "1",
            },
        },
    }));

    await start();
    const voip = getService("voip");
    patch(voip.action, {
        currentController: {
            props: { type: "form", resModel: "res.partner" },
            currentState: { resId: 42 },
        },
    });

    await click(".o_menu_systray button:has(> [data-icon='phone'])");
    await contains(".o-voip-Keypad-input:value('+1 234 567 8900')");
    await waitUntil(() => voip.softphone.dialer.input.country?.code === "US");
    await click(".o_menu_systray button:has(> [data-icon='phone'])");
    await waitUntil(() => !voip.softphone.isDisplayed);
    voip.softphone.dialer.input.country = null;

    await click(".o_menu_systray button:has(> [data-icon='phone'])");
    await contains(".o-voip-Keypad-input:value('+1 234 567 8900')");
    await waitUntil(() => voip.softphone.dialer.input.country?.code === "US");
});

test("stale phone parsing does not overwrite a newer prefill", async () => {
    const secondPrefillDef = Promise.withResolvers();
    onRpc("voip.call", "get_prefill_data", async ({ args }) => {
        if (args[1] === 2) {
            await secondPrefillDef.promise;
        }
        return {
            partner_id: args[1],
            phone: args[1] === 1 ? "+15550001" : "+325550002",
            store_data: {},
        };
    });
    const firstParseDef = Promise.withResolvers();
    const firstParseHandledDef = Promise.withResolvers();
    let parseCount = 0;
    onRpc("/voip/parse_phone_number", async (request) => {
        const { params } = await request.json();
        parseCount++;
        if (parseCount === 1) {
            await firstParseDef.promise;
            firstParseHandledDef.resolve();
        }
        const isFirstPhone = params.data.phone_number === "+15550001";
        return {
            countryId: isFirstPhone ? 2 : 1,
            isValid: true,
            phone_number: isFirstPhone ? "+1 555 0001" : "+32 555 00 02",
            storeData: {
                "res.country": {
                    id: isFirstPhone ? 2 : 1,
                    name: isFirstPhone ? "United States" : "Belgium",
                    code: isFirstPhone ? "US" : "BE",
                    phone_code: isFirstPhone ? "1" : "32",
                },
            },
        };
    });

    await start();
    const voip = getService("voip");
    const controller = {
        props: { type: "form", resModel: "res.partner" },
        currentState: { resId: 1 },
    };
    patch(voip.action, { currentController: controller });
    await click(".o_menu_systray button:has(> [data-icon='phone'])");
    await waitUntil(() => parseCount === 1);

    controller.currentState.resId = 2;
    const secondPrefillProm = voip.prefillFromActiveForm("res.partner", 2);
    expect(voip.softphone.dialer.input.value).toBe("");
    firstParseDef.resolve();
    await firstParseHandledDef.promise;
    await animationFrame();
    expect(voip.softphone.dialer.input.value).toBe("");

    secondPrefillDef.resolve();
    await secondPrefillProm;
    await contains(".o-voip-Keypad-input:value('+32 555 00 02')");
    expect(voip.softphone.dialer.prefillContext).toEqual({
        resModel: "res.partner",
        resId: 2,
        partnerId: 2,
    });
});

test("prefill is skipped when no form is open", async () => {
    await start();
    onRpc("voip.call", "get_prefill_data", () => {
        throw new Error("get_prefill_data should not be called when no form is open");
    });

    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("button[data-tab='recent'].active");
});

test("prefill is skipped when controller type is not form", async () => {
    await start();
    const action = getService("action");
    patch(action, {
        currentController: {
            props: { type: "list", resModel: "res.partner" },
            currentState: { resId: 1 },
        },
    });
    onRpc("voip.call", "get_prefill_data", () => {
        throw new Error("get_prefill_data should not be called when controller type is not form");
    });

    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("button[data-tab='recent'].active");
});

test("prefill is silently ignored on AccessError", async () => {
    await start();
    const action = getService("action");
    patch(action, {
        currentController: {
            props: { type: "form", resModel: "res.partner" },
            currentState: { resId: 1 },
        },
    });
    onRpc("voip.call", "get_prefill_data", () => {
        const error = new Error("Access denied");
        error.name = "odoo.exceptions.AccessError";
        throw error;
    });

    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("button[data-tab='recent'].active");
});

test("prefill and direct call passes form context", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({
        name: "Call Target",
        phone: "+1 (234) 567-8900",
    });
    await start();
    const action = getService("action");
    patch(action, {
        currentController: {
            props: { type: "form", resModel: "res.partner" },
            currentState: { resId: partnerId },
        },
    });
    onRpc("voip.call", "get_prefill_data", () => ({
        partner_id: partnerId,
        phone: "+1 234 567 8900",
        store_data: {
            "res.partner": [
                {
                    id: partnerId,
                    name: "Call Target",
                    complete_name: "Call Target",
                    phone: "+1 (234) 567-8900",
                },
            ],
        },
    }));

    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("button[data-tab='dialer'].active");
    await click("button[title='Call']");

    // An activity should have been created on the form record
    expect(
        pyEnv["mail.activity"].search_count([
            ["res_model", "=", "res.partner"],
            ["res_id", "=", partnerId],
        ])
    ).toBe(1);
});

test("prefill and related partner suggestion passes form context", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({
        name: "Call Target",
        phone: "+1 (234) 567-8900",
    });
    await start();
    const voip = getService("voip");
    patch(voip.action, {
        currentController: {
            props: { type: "form", resModel: "res.partner" },
            currentState: { resId: partnerId },
        },
    });
    onRpc("voip.call", "get_prefill_data", () => ({
        partner_id: partnerId,
        phone: "+1 234 567 8900",
        store_data: {
            "res.partner": [
                {
                    id: partnerId,
                    name: "Call Target",
                    complete_name: "Call Target",
                    phone: "+1 (234) 567-8900",
                },
            ],
        },
    }));

    await click(".o_menu_systray button:has(> [data-icon='phone'])");
    await contains("button[data-tab='dialer'].active");
    await click(".o-voip-Keypad button[data-tooltip]");

    expect(
        pyEnv["mail.activity"].search_count([
            ["res_model", "=", "res.partner"],
            ["res_id", "=", partnerId],
        ])
    ).toBe(1);
});

test("prefill and unrelated partner suggestion skips form context", async () => {
    const pyEnv = await startServer();
    const relatedPartnerId = pyEnv["res.partner"].create({
        name: "Z Related Partner",
        phone: "+1 (234) 567-8900",
    });
    const otherPartnerId = pyEnv["res.partner"].create({
        name: "A Other Partner",
        phone: "+1 (234) 567-8900",
    });
    await start();
    const voip = getService("voip");
    patch(voip.action, {
        currentController: {
            props: { type: "form", resModel: "res.partner" },
            currentState: { resId: relatedPartnerId },
        },
    });
    onRpc("voip.call", "get_prefill_data", () => ({
        partner_id: relatedPartnerId,
        phone: "+1 234 567 8900",
        store_data: {
            "res.partner": [
                {
                    id: relatedPartnerId,
                    name: "Z Related Partner",
                    complete_name: "Z Related Partner",
                    phone: "+1 (234) 567-8900",
                },
            ],
        },
    }));

    await click(".o_menu_systray button:has(> [data-icon='phone'])");
    await contains("button[data-tab='dialer'].active");
    voip.store.insert({
        "res.partner": [
            {
                id: otherPartnerId,
                name: "A Other Partner",
                complete_name: "A Other Partner",
                phone: "+1 (234) 567-8900",
            },
        ],
    });
    await contains(".o-voip-Keypad button:has(i[data-icon='group'])");
    const callCount = pyEnv["voip.call"].search_count([]);
    await click(".o-voip-Keypad button[data-tooltip]");
    await waitUntil(() => pyEnv["voip.call"].search_count([]) > callCount);

    expect(
        pyEnv["mail.activity"].search_count([
            ["res_model", "=", "res.partner"],
            ["res_id", "=", relatedPartnerId],
        ])
    ).toBe(0);
});

test("prefill and call with modified number skips form context", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({
        name: "Call Target",
        phone: "+1 (234) 567-8900",
    });
    await start();
    const action = getService("action");
    patch(action, {
        currentController: {
            props: { type: "form", resModel: "res.partner" },
            currentState: { resId: partnerId },
        },
    });
    onRpc("voip.call", "get_prefill_data", () => ({
        partner_id: partnerId,
        phone: "+1 234 567 8900",
        store_data: {
            "res.partner": [
                {
                    id: partnerId,
                    name: "Call Target",
                    complete_name: "Call Target",
                    phone: "+1 (234) 567-8900",
                },
            ],
        },
    }));

    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("button[data-tab='dialer'].active");
    await contains(".o-voip-Keypad-input:value('+1 234 567 8900')");
    // Modify the pre-filled number before calling
    await click(".o-voip-Keypad-backspace");
    await click(".o-voip-Keypad-backspace");
    await click("button[title='Call']");

    // No activity should be created since the number was modified
    expect(
        pyEnv["mail.activity"].search_count([
            ["res_model", "=", "res.partner"],
            ["res_id", "=", partnerId],
        ])
    ).toBe(0);
});

test("prefill and call from recent tab skips form context", async () => {
    const pyEnv = await startServer();
    const formPartnerId = pyEnv["res.partner"].create({
        name: "Form Partner",
        phone: "+1 (234) 567-8900",
    });
    const otherPartnerId = pyEnv["res.partner"].create({
        name: "Other Partner",
        phone: "+1 (999) 888-7777",
    });
    pyEnv["voip.call"].create({
        partner_id: otherPartnerId,
        phone_number: "+1 (999) 888-7777",
        state: "terminated",
        user_id: serverState.userId,
    });
    await start();
    const action = getService("action");
    patch(action, {
        currentController: {
            props: { type: "form", resModel: "res.partner" },
            currentState: { resId: formPartnerId },
        },
    });
    onRpc("voip.call", "get_prefill_data", () => ({
        partner_id: formPartnerId,
        phone: "+1 234 567 8900",
        store_data: {
            "res.partner": [
                {
                    id: formPartnerId,
                    name: "Form Partner",
                    complete_name: "Form Partner",
                    phone: "+1 (234) 567-8900",
                },
            ],
        },
    }));

    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("button[data-tab='dialer'].active");
    await contains(".o-voip-Keypad-input:value('+1 234 567 8900')");
    // Call another number from the Recent tab
    await click("button[data-tab='recent']");
    await contains(".o-voip-TabEntry:contains('Other Partner') button[title='Call']");
    await click(".o-voip-TabEntry:contains('Other Partner') button[title='Call']");

    // No activity should be created on the form record
    expect(
        pyEnv["mail.activity"].search_count([
            ["res_model", "=", "res.partner"],
            ["res_id", "=", formPartnerId],
        ])
    ).toBe(0);
});
