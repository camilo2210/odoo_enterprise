import { animationFrame, describe, expect, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";

import { click, contains, start, startServer, insertText } from "@mail/../tests/mail_test_helpers";

import { ResUsers } from "@voip/../tests/mock_server/mock_models/res_users";
import { receiveInvite, setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { getService, onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("outgoing call shows pending state until established", async () => {
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Dialer input", "123456");
    await click(".o-voip-Dialer > .o-voip-Keypad-numpad .o-voip-ActionButton");

    await contains(".o-voip-InCallView-statusWrapper", { text: "Calling..." });
    await contains(".o-voip-InCallView-pad button:has([data-icon='sync_alt']):disabled.opacity-25");
    await contains(".o-voip-InCallView-pad button:has([data-icon='add']):disabled.opacity-25");
    await contains(".o-voip-InCallView-pad button:has([data-icon='pause']):disabled.opacity-25");
    await contains(
        ".o-voip-InCallView-pad button:has([data-icon='mic_off']):enabled:not(.opacity-25)"
    );
    await contains(
        ".o-voip-InCallView-pad button:has([data-icon='dialpad']):enabled:not(.opacity-25)"
    );
    await contains(".o-voip-InCallView-pad button:has(.o-voip-CallIcon-end):enabled");

    await advanceTime(SIP.Inviter.INVITE_DELAY + 1);
    await contains(".o-voip-InCallView-statusWrapper", { text: "00:00" });
    await contains(".o-voip-InCallView-pad button:has([data-icon='sync_alt']):enabled");
    await contains(".o-voip-InCallView-pad button:has([data-icon='add']):enabled");
    await contains(".o-voip-InCallView-pad button:has([data-icon='pause']):enabled");
    await contains(".o-voip-InCallView-pad button:has([data-icon='mic_off']):enabled");
    await contains(".o-voip-InCallView-pad button:has([data-icon='dialpad']):enabled");
});

test("an outgoing call with multiple DIDs shows the selected caller ID", async () => {
    const outboundNumber = {
        countryId: 1,
        countryName: "Belgium",
        flagUrl: "/base/static/img/flags/be.png",
        formatted: "+32 470 00 00 01",
        number: "+32470000001",
    };
    const config = {
        didNumber: outboundNumber.number,
        didNumberFormatted: outboundNumber.formatted,
        didNumberState: "active",
        isInternalCallingProvisioned: true,
        usesOdooProvider: true,
        missedCalls: 0,
        mode: "demo",
        outboundCallerId: outboundNumber.number,
        outboundNumbers: [
            outboundNumber,
            {
                countryId: 2,
                countryName: "France",
                flagUrl: "/base/static/img/flags/fr.png",
                formatted: "+33 1 23 45 67 89",
                number: "+33123456789",
            },
        ],
        pbxAddress: "localhost",
        pbxExtensionNumber: "1000",
        recordingPolicy: "disabled",
        sharedOutboundNumbers: [],
        webSocketUrl: "ws://localhost",
        voicemailCode: null,
    };
    const initStoreData = ResUsers.prototype._init_store_data;
    patchWithCleanup(ResUsers.prototype, {
        _init_store_data(store) {
            initStoreData.call(this, store);
            store.add_global_values({ voipConfig: config });
        },
    });
    onRpc("voip.call", "resolve_outgoing_dial_number", () => ({
        is_internal: false,
        number: "+3212345678",
    }));
    onRpc("get_current_voip_config", () => ({ voipConfig: config, settings: false }));
    await start();
    getService("voip").setAutoSelectCallerId(true);
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Dialer input", "+3212345678");
    await click(".o-voip-Dialer > .o-voip-Keypad-numpad .o-voip-ActionButton");

    await contains(".o-voip-InCallView-statusWrapper span.d-flex > span:first-child", {
        text: "Via",
    });
    expect(getService("voip").userAgent.frontSession.outboundNumber).toEqual(outboundNumber);
    await contains(
        ".o-voip-InCallView-statusWrapper img[data-src='/base/static/img/flags/be.png']"
    );
    await contains(".o-voip-InCallView-statusWrapper span.d-flex > span:last-child", {
        text: "+32 470 00 00 01",
    });
});

test("clicking mute and hold buttons toggles mock SIP session tracks", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-mute-hold" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button:has([data-icon='phone'])");
    await contains(".o-voip-InCallView");

    const sipSession = getService("voip").userAgent.frontSession.__sipJsSession;
    const senderTrack = sipSession.sessionDescriptionHandler.peerConnection.getSenders()[0].track;
    expect(senderTrack.enabled).toBe(true);

    const muteButtonSelector = ".o-voip-InCallView-pad button:has([data-icon='mic_off'])";
    await contains(`${muteButtonSelector}:not(.active)`);

    await click(muteButtonSelector);
    expect(senderTrack.enabled).toBe(false);
    await contains(`${muteButtonSelector}.active`);

    await click(muteButtonSelector);
    expect(senderTrack.enabled).toBe(true);
    await contains(`${muteButtonSelector}:not(.active)`);

    const holdButtonSelector = ".o-voip-InCallView-pad button:has([data-icon='pause'])";
    await contains(`${holdButtonSelector}:not(.active)`);

    await click(holdButtonSelector);
    expect(senderTrack.enabled).toBe(false);
    await contains(`${holdButtonSelector}.active`);
    await contains(".o-voip-Softphone header [data-icon='pause'].text-warning");

    await click(holdButtonSelector);
    expect(senderTrack.enabled).toBe(true);
    await contains(`${holdButtonSelector}:not(.active)`);
    // The toggle may then show the microphone status, so only assert that hold is cleared here.
    await contains(".o-voip-StatusMenu-callStatus > [data-icon='pause']", { count: 0 });
});

test("transfer contact entry stays open when the call timer updates", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([{ name: "Transfer Contact", phone: "+1-307-555-0120" }]);
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-transfer-contact" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button:has([data-icon='phone'])");
    await contains(".o-voip-InCallView");

    await click(".o-voip-InCallView-pad button:has([data-icon='sync_alt'])");
    await contains(".o-voip-TransferView .o-voip-TabEntry", { count: 1 });
    await contains(".o-voip-TransferView .o-voip-TabEntry summary .o-voip-ActionButton");
    await click(".o-voip-TransferView .o-voip-TabEntry-title");
    await contains(".o-voip-TransferView .o-voip-TabEntry details[open]");
    await contains(".o-voip-TransferView .o-voip-TabEntry summary .o-voip-ActionButton", {
        count: 0,
    });

    await advanceTime(2000);
    await animationFrame();
    expect(".o-voip-TransferView .o-voip-TabEntry details").toHaveAttribute("open");
});

test("clicking contact button opens contact form for existing contacts", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([{ name: "Adel Shakal", phone: "+1-307-555-0120" }]);
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='recent']");
    await insertText("input[id='o-voip-Tab-searchInput']", "Adel Shakal");
    await click(".o-voip-TabEntry:contains('Adel Shakal') summary button[title='Call']");
    await click("button[title='Go to']");
    await contains("span.o-dropdown-item i[data-icon='person']");
    await click("span.o-dropdown-item span:contains('Contact')");
    await contains(".o_form_sheet");
    await contains("div[name='name'] input", { value: "Adel Shakal" });
});

test("clicking contact button opens contact form for unknown numbers", async () => {
    const TEST_PHONE_NUMBER = "+1-555-123-4567";
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Dialer input", TEST_PHONE_NUMBER);
    await click("button[title='Call']");
    await contains("button[title='Create']");
    await click("button[title='Create']");
    await contains("span.o-dropdown-item i[data-icon='person']");
    await click("span.o-dropdown-item span:contains('Contact')");
    await contains(".o_form_sheet");
});
