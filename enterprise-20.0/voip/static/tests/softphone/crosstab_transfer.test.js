import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test, waitUntil } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import { openSoftphone, receiveInvite, setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { UserAgent } from "@voip/core/web/user_agent";
import { MockServer, onRpc, patchWithCleanup, serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();
patchWithCleanup(UserAgent.prototype, { _setupLocalAgentUUIDs() {} });

async function setupProdMode() {
    const pyEnv = await startServer();
    const providerId = pyEnv["voip.provider"].create({ mode: "prod" });
    pyEnv["res.users"].write([serverState.userId], { voip_provider_id: providerId });
    pyEnv["res.users.settings"].create({
        voip_secret: "super secret password",
        voip_username: "1337",
        user_id: serverState.userId,
    });
}

function muteRejectedReferWarning() {
    const originalConsoleWarn = console.warn.bind(console);
    patchWithCleanup(console, {
        warn(message, error, ...args) {
            if (error?.message !== "REFER rejected") {
                originalConsoleWarn(message, error, ...args);
            }
        },
    });
}

async function answerCall(env) {
    await click(`${env.selector} .o-voip-CallInvitation button[title='Accept the call']`);
    await contains(`${env.selector} .o-voip-InCallView`);
}

async function hangUp(env) {
    await click(`${env.selector} .o-voip-InCallView-pad button[title='Hang up']`);
}

test("only one tab leads the ringtone for the same incoming call", async () => {
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    await Promise.all([
        tab1.services.worker_service.ensureWorkerStarted(),
        tab2.services.worker_service.ensureWorkerStarted(),
    ]);
    patchWithCleanup(navigator.userActivation, { hasBeenActive: true });

    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab2);

    const sessions = [tab1.services.voip.userAgent, tab2.services.voip.userAgent].map(
        (userAgent) => userAgent.callInvitationSession
    );
    await waitUntil(() => sessions.some((session) => session.ringleader));
    expect(sessions.filter((session) => session.ringleader).length).toBe(1);
});

test("Banner appears when another tab has an active call.", async () => {
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    await contains(`${tab2.selector} button:text(Switch here)`, { count: 0 });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    await contains(`${tab2.selector} button:text(Switch here)`);
});

test("Banner disappears when the other tab hangs up.", async () => {
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    await contains(`${tab2.selector} button:text(Switch here)`);
    await hangUp(tab1);
    await contains(`${tab2.selector} button:text(Switch here)`, { count: 0 });
});

test("Banner does not appear for the tab's own calls.", async () => {
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    await contains(`${tab1.selector} button:text(Switch here)`, { count: 0 });
});

test("Clicking 'Switch here' triggers the pull flow.", async () => {
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    await click(`${tab2.selector} button:text(Switch here)`);
    await contains(`${tab2.selector} .o-voip-InCallView`);
    await contains(`${tab1.selector} .o-voip-InCallView`, { count: 0 });
    await contains(".o_notification:contains(Transferred 1 call)");
});

test("Banner disappears on source tab after successful pull.", async () => {
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    await click(`${tab2.selector} button:text(Switch here)`);
    await contains(`${tab2.selector} .o-voip-InCallView`);
    await contains(`${tab1.selector} .o-voip-InCallView`, { count: 0 });
    await contains(`${tab2.selector} button:text(Switch here)`, { count: 0 });
});

test("'Switching calls' notification appears immediately.", async () => {
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    await click(`${tab2.selector} button:text(Switch here)`);
    await contains(`.o_notification:contains(Switching calls to this tab)`);
    await contains(`${tab2.selector} .o-voip-InCallView`);
});

test("Puller sees success stats after pull.", async () => {
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    await click(`${tab2.selector} button:text(Switch here)`);
    await contains(`${tab2.selector} .o-voip-InCallView`);
    await contains(".o_notification:contains(Switched 1 call)");
});

test("a rejected REFER immediately reports a failed cross-tab transfer", async () => {
    muteRejectedReferWarning();
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    const sourceUserAgent = tab1.services.voip.userAgent;
    patchWithCleanup(sourceUserAgent.frontSession.__sipJsSession, {
        refer(_target, { requestDelegate }) {
            requestDelegate.onReject(new Error("REFER rejected"));
            return Promise.resolve();
        },
    });

    await click(`${tab2.selector} button:text(Switch here)`);

    await contains(".o_notification:contains(Failed to transfer 1 call)");
    await contains(`${tab1.selector} .o-voip-InCallView`);
    await contains(`${tab2.selector} .o-voip-InCallView`, { count: 0 });
    await waitUntil(() => sourceUserAgent.push === null);
    expect(sourceUserAgent.push).toBe(null);
    expect(tab2.services.voip.userAgent.pull).toBe(null);
});

test("a pull timeout only ends the call whose replacement INVITE never arrived", async () => {
    muteRejectedReferWarning();
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    receiveInvite({ phone_number: "9876543210", sip_call_id: "invite-002" }, tab1);
    await answerCall(tab1);
    const sourceUserAgent = tab1.services.voip.userAgent;
    // Matched by creation order rather than phone_number: the session's
    // phone_number can be reformatted once its call record resolves.
    const [rejectedSession, strandedSession] = Object.values(sourceUserAgent.sessions);
    patchWithCleanup(rejectedSession.__sipJsSession, {
        refer(_target, { requestDelegate }) {
            requestDelegate.onReject(new Error("REFER rejected"));
            return Promise.resolve();
        },
    });
    patchWithCleanup(strandedSession.__sipJsSession, {
        refer(_target, { requestDelegate }) {
            // Accepted, but its replacement INVITE is never sent to tab2 —
            // simulates the PBX dropping it after the REFER succeeded.
            requestDelegate.onAccept();
            return Promise.resolve();
        },
    });

    await click(`${tab2.selector} button:text(Switch here)`);
    const pullerUserAgent = tab2.services.voip.userAgent;
    // The rejected entry settles quickly; the stranded one never does on its
    // own — only the 20s safety timeout resolves it.
    await waitUntil(() => pullerUserAgent.pull?.pendingEntries.some((e) => e.settled));
    await advanceTime(20_000);
    await contains(".o_notification:contains(Failed to transfer 2 calls)");

    // Each INVITE is correlated by its Call-ID, which lives on the call's leg.
    const callIdFor = (sipCallId) =>
        MockServer.env["voip.call.leg"]._find_call_id(sipCallId);
    const [rejectedCall] = MockServer.env["voip.call"].search_read(
        [["id", "=", callIdFor("invite-001")]],
        ["state"]
    );
    const [strandedCall] = MockServer.env["voip.call"].search_read(
        [["id", "=", callIdFor("invite-002")]],
        ["state"]
    );
    expect(rejectedCall.state).not.toBe("terminated");
    expect(strandedCall.state).toBe("terminated");
});

test("pullAllCalls is blocked while already pulling.", async () => {
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    await contains(`${tab2.selector} button:text(Switch here)`);
    const { promise } = Promise.withResolvers();
    onRpc("res.users", "action_voip_bus_send", async ({ args }) => {
        const [message_type] = args;
        if (message_type === "voip.call.pull/initiate") {
            expect.step(message_type);
            await promise;
        }
    });
    await click(`${tab2.selector} button:text(Switch here)`);
    expect.verifySteps(["voip.call.pull/initiate"]);
    await click(`${tab2.selector} button:text(Switch here)`);
    expect.verifySteps([]);
});

test("Source tab rejects a second pull request.", async () => {
    await setupProdMode();
    const tab1 = await start({ asTab: true });
    await openSoftphone({ selector: tab1.selector });
    const tab2 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab2.selector });
    const tab3 = await start({ asTab: true, waitUntilSubscribe: false });
    await openSoftphone({ selector: tab3.selector });
    receiveInvite({ phone_number: "0123456789", sip_call_id: "invite-001" }, tab1);
    await answerCall(tab1);
    const { promise, resolve } = Promise.withResolvers();
    onRpc("res.users", "action_voip_bus_send", async ({ args }) => {
        const [message_type] = args;
        if (message_type === "voip.call.pull/pending_entries") {
            expect.step(message_type);
            await promise;
        }
    });
    await click(`${tab2.selector} button:text(Switch here)`);
    await click(`${tab3.selector} button:text(Switch here)`);
    resolve();
    await contains(`${tab1.selector} .o-voip-InCallView`, { count: 0 });
    await contains(`${tab2.selector} .o-voip-InCallView`, { count: 1 });
    await contains(`${tab3.selector} .o-voip-InCallView`, { count: 0 });
    expect.verifySteps(["voip.call.pull/pending_entries"]);
});
