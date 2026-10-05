import {
    click,
    contains,
    insertText,
    start,
    startServer,
    triggerHotkey,
} from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, runAllTimers, tick } from "@odoo/hoot-mock";
import { receiveInvite, setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { getService, onRpc } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Accepting a second incoming call puts the first on hold.", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    receiveInvite({ phone_number: "9876543210", sip_call_id: "invite-002" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    const { userAgent } = getService("voip");
    expect(Object.keys(userAgent.sessions).length).toBe(2);
    await contains(".o-voip-CallBanner");
    await contains(".o-voip-CallBanner [data-icon='pause']");
    await contains(".o-voip-CallBanner", { text: "0123456789" });
});

test("Multiple back session banners with 3 active calls.", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    receiveInvite({ phone_number: "9876543210", sip_call_id: "invite-002" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    receiveInvite({ phone_number: "5551112222", sip_call_id: "invite-003" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    await contains(".o-voip-ContactInfo", { text: "5551112222" });
    await contains(".o-voip-CallBanner", { count: 2 });
    await contains(".o-voip-CallBanner", { text: "9876543210" });
    await contains(".o-voip-CallBanner", { text: "0123456789" });
});

test("Switching between calls via back session banner.", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    receiveInvite({ phone_number: "9876543210", sip_call_id: "invite-002" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    await contains(".o-voip-ContactInfo", { text: "9876543210" });
    await contains(".o-voip-CallBanner", { text: "0123456789" });

    await click(".o-voip-CallBanner > button");
    await contains(".o-voip-ContactInfo", { text: "0123456789" });
    await contains(".o-voip-CallBanner", { text: "9876543210" });
});

test("Hanging up front session promotes back session.", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    receiveInvite({ phone_number: "9876543210", sip_call_id: "invite-002" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    const { userAgent } = getService("voip");
    expect(Object.keys(userAgent.sessions).length).toBe(2);

    await click(".o-voip-InCallView-pad button[title='Hang up']");
    expect(Object.keys(userAgent.sessions).length).toBe(1);
    await contains(".o-voip-InCallView");
    await contains(".o-voip-ContactInfo", { text: "0123456789" });
    await contains(".o-voip-CallBanner", { count: 0 });
});

test("Rejecting incoming call during active call.", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    receiveInvite({ phone_number: "9876543210", sip_call_id: "invite-002" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Reject the call']");

    await contains(".o-voip-InCallView");
    await contains(".o-voip-CallInvitation", { count: 0 });
    const { userAgent } = getService("voip");
    expect(Object.keys(userAgent.sessions).length).toBe(1);
    await contains(".o-voip-ContactInfo", { text: "0123456789" });
});

test("Add Call button initiates outgoing call during active call.", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");

    await click("button[title='Add Call']");
    await contains(".o-voip-AddCallView");
    await click("button[title='Keypad']");
    await contains(".o-voip-Keypad-searchBar input");
    await insertText(".o-voip-Keypad-searchBar input", "5551234567");
    await triggerHotkey("Enter");
    await tick();
    await advanceTime(5000);
    const { userAgent } = getService("voip");
    expect(Object.keys(userAgent.sessions).length).toBe(2);
});

test("Transfer view: Direct (blind) transfer.", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");

    await click("button[title='Transfer']");
    await contains(".o-voip-TransferView");
    await click("button[title='Keypad']");
    await contains(".o-voip-Keypad-searchBar input");
    await insertText(".o-voip-Keypad-searchBar input", "5559876543");
    await click(".o-voip-TransferView button[title='Transfer']");
    await contains("button[title='Transfer Now'] i[data-icon='phone_forwarded']");
    await click("button[title='Transfer Now']");
    const { userAgent } = getService("voip");
    expect(Object.keys(userAgent.sessions).length).toBe(0);
});

test("Transfer contact search sorts internal users first", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        {
            name: "Odoo Transfer External",
            phone: "+1 555-540-4899",
            partner_share: true,
        },
        {
            name: "Odoo Transfer Internal",
            phone: "+1 555-540-4888",
            partner_share: false,
        },
    ]);
    let initialSearchChecked = false;
    onRpc("res.partner", "get_contacts", (args) => {
        if (args.kwargs.search_terms === "Odoo Transfer") {
            expect(args.kwargs.internal_users_first).toBe(true);
            if (args.kwargs.offset === 0 && !initialSearchChecked) {
                initialSearchChecked = true;
                expect.step("search transfer contacts");
            }
        }
    });
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");

    await click("button[title='Transfer']");
    await insertText(".o-voip-TransferView input[id='o-voip-Tab-searchInput']", "Odoo Transfer");
    await runAllTimers();
    await contains(".o-voip-TransferView .o-voip-TabEntry-title", {
        text: "Odoo Transfer Internal",
    });
    await contains(".o-voip-TransferView .o-voip-TabEntry-title", {
        text: "Odoo Transfer External",
    });
    await contains(".o-voip-TransferView .o-voip-AddressBook h2", { count: 0 });
    const contacts = Array.from(
        document.querySelectorAll(".o-voip-TransferView .o-voip-TabEntry-title"),
        (node) => node.textContent.trim()
    );
    expect(contacts).toEqual(["Odoo Transfer Internal", "Odoo Transfer External"]);
    expect.verifySteps(["search transfer contacts"]);
});

test("Transfer view: Attended transfer (Ask First) and Confirm Transfer.", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    const { userAgent } = getService("voip");
    const mainSessionKey = userAgent.frontSession.key;

    await click("button[title='Transfer']");
    await contains(".o-voip-TransferView");
    await click("button[title='Keypad']");
    await contains(".o-voip-Keypad-searchBar input");
    await insertText(".o-voip-Keypad-searchBar input", "5559876543");
    await click(".o-voip-TransferView button[title='Transfer']");
    await contains("button[title='Ask First'] i[data-icon='phone_paused']");
    await click("button[title='Ask First']");
    await tick();
    await advanceTime(5000);

    const transferSessionKey = userAgent.frontSession.key;
    expect(Object.keys(userAgent.sessions).length).toBe(2);
    expect(userAgent.transferPairs.length).toBe(1);
    expect(userAgent.transferPairs[0]).toEqual([mainSessionKey, transferSessionKey]); // Verify asymmetric pair direction: main → transfer (not reversed)
    await click("button[title='Confirm Transfer']");
    expect(Object.keys(userAgent.sessions).length).toBe(0);
    expect(userAgent.transferPairs.length).toBe(0);
});

test("Transfer confirmation: back arrow cancels the transfer.", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");

    await click("button[title='Transfer']");
    await contains(".o-voip-TransferView");
    await click("button[title='Keypad']");
    await contains(".o-voip-Keypad-searchBar input");
    await insertText(".o-voip-Keypad-searchBar input", "5559876543");
    await click(".o-voip-TransferView button[title='Transfer']");
    await contains(".o-voip-Softphone header button[title='Back']");
    await click(".o-voip-Softphone header button[title='Back']");
    await contains(".o-voip-TransferView input[id='o-voip-Tab-searchInput']");
});

test("Back session banners hidden during transfer and add-call views.", async () => {
    await start();
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    receiveInvite({ phone_number: "9876543210", sip_call_id: "invite-002" });
    await contains(".o-voip-CallInvitation");
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    await contains(".o-voip-CallBanner"); // In default view, back session banner is visible
    await click("button[title='Transfer']"); // Click Transfer → banners should be hidden
    await contains(".o-voip-TransferView");
    await contains(".o-voip-CallBanner", { count: 0 });
});
