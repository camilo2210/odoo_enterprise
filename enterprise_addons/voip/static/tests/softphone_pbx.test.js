import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { receiveInvite, setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { onRpc, serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Incoming invite with existing Call-ID retrieves the existing call.", async () => {
    const pyEnv = await startServer();
    const sipCallId = "invite-existing-call";
    const callId = pyEnv["voip.call"].create({
        phone_number: "+3287654321",
        direction: "incoming",
        state: "calling",
        user_id: serverState.userId,
    });
    // The Call-ID lives on the call's leg, which is what correlates this
    // INVITE with the call the webhook already created.
    pyEnv["voip.call.leg"].create({ sip_call_id: sipCallId, voip_call_id: callId });
    await start();
    onRpc("voip.call", "get_or_create", ({ args }) => {
        expect.step(`get_or_create:${args[0].sip_call_id}`);
    });
    onRpc("voip.call", "start_call", () => {
        expect.step("start_call");
    });
    onRpc("voip.call", "end_call", () => {
        expect.step("end_call");
    });
    receiveInvite({
        phone_number: "+3287654321",
        sip_call_id: sipCallId,
    });
    await contains(".o-voip-CallInvitation");
    expect.verifySteps([`get_or_create:${sipCallId}`]);
    // Accept the existing PBX call and hang up: the browser still drives the
    // Odoo call state for non-Odoo providers.
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    await click(".o-voip-InCallView button[title='Hang up']");
    await contains(".o-voip-InCallView", { count: 0 });
    expect.verifySteps(["start_call", "end_call"]);
});

test("Incoming invite without X-Odoo-Call-ID creates a new call and manages state.", async () => {
    await start();
    onRpc("voip.call", "get_or_create", ({ args }) => {
        expect.step(`get_or_create:${args[0].id ?? "no-id"}`);
    });
    onRpc("voip.call", "start_call", () => {
        expect.step("start_call");
    });
    onRpc("voip.call", "end_call", () => {
        expect.step("end_call");
    });
    receiveInvite({ phone_number: "+3287654321", sip_call_id: "invite-001" });
    await contains(".o-voip-CallInvitation");
    expect.verifySteps(["get_or_create:no-id"]);
    // Accept the call and hang up — skipServerUpdate is not disabled so RPCs are sent.
    await click(".o-voip-CallInvitation button[title='Accept the call']");
    await contains(".o-voip-InCallView");
    expect.verifySteps(["start_call"]);
    await click(".o-voip-InCallView button[title='Hang up']");
    await contains(".o-voip-InCallView", { count: 0 });
    expect.verifySteps(["end_call"]);
});

test("Wazo forked invite uses X-Odoo-Conversation-Id as the shared conversation.", async () => {
    const pyEnv = await startServer();
    pyEnv["voip.provider"].write([1], { is_odoo_provider: true });
    pyEnv["res.users"].write([serverState.userId], { voip_provider_id: 1 });
    await start();
    onRpc("voip.call", "get_or_create", ({ args }) => {
        expect.step(`get_or_create:${args[0].conversation_identifier ?? "none"}:${args[0].sip_call_id}`);
    });
    receiveInvite({
        phone_number: "+3287654321",
        sip_call_id: "per-tab-call-id",
        headers: { "X-Odoo-Conversation-Id": "conv-shared" },
    });
    await contains(".o-voip-CallInvitation");
    expect.verifySteps(["get_or_create:conv-shared:per-tab-call-id"]);
});

test("X-Odoo-Conversation-Id is ignored for non-Odoo providers.", async () => {
    await start();
    onRpc("voip.call", "get_or_create", ({ args }) => {
        expect.step(`get_or_create:${args[0].conversation_identifier ?? "none"}:${args[0].sip_call_id}`);
    });
    receiveInvite({
        phone_number: "+3287654321",
        sip_call_id: "per-tab-call-id",
        headers: { "X-Odoo-Conversation-Id": "conv-forged" },
    });
    await contains(".o-voip-CallInvitation");
    expect.verifySteps(["get_or_create:none:per-tab-call-id"]);
});

test("Incoming invite displays the formatted phone number.", async () => {
    const pyEnv = await startServer();
    const sipCallId = "invite-formatted";
    const callId = pyEnv["voip.call"].create({
        phone_number: "+3287654321",
        phone_number_formatted: "+32 87 65 43 21",
        direction: "incoming",
        state: "calling",
        user_id: serverState.userId,
    });
    pyEnv["voip.call.leg"].create({ sip_call_id: sipCallId, voip_call_id: callId });
    await start();
    receiveInvite({ phone_number: "+3287654321", sip_call_id: sipCallId });
    // The screen shows the INTERNATIONAL-formatted number, not the raw digits.
    await contains(".o-voip-CallInvitation .o-voip-PhoneNumber", { text: "+32 87 65 43 21" });
});
