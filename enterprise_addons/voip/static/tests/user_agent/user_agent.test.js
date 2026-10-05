import { start, startServer } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import { receiveInvite, setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { AudioManager } from "@voip/core/web/audio_manager";
import { getService, onRpc, patchWithCleanup, serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

// allow test data to be overridden in other modules
const settingsData = {
    voip_secret: "super secret password",
    voip_username: "1337",
};
const expectedValues = {
    authorizationUsername: settingsData.voip_username,
};

test("SIP.js user agent configuration is set correctly.", async (assert) => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({
        ...settingsData,
        user_id: serverState.userId,
    });
    await start();
    const config = (await getService("voip")).userAgent.sipJsUserAgentConfig;
    expect(config.authorizationPassword).toBe("super secret password");
    expect(config.authorizationUsername).toBe(expectedValues.authorizationUsername);
    expect(config.uri.raw.user).toBe("1337");
    expect(config.uri.raw.host).toBe("localhost");
});

test("Contact URI keeps the AOR user part and carries a unique per UA parameter.", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({
        ...settingsData,
        user_id: serverState.userId,
    });
    await start();
    const voipService = await getService("voip");
    patchWithCleanup(voipService.config, { usesOdooProvider: true });
    const { userAgent } = voipService;
    const config = userAgent.sipJsUserAgentConfig;
    expect(config.contactName).toBe(settingsData.voip_username);
    expect(config.contactParams.transport).toBe("ws");
    expect(config.contactParams["x-odoo-unique"]).not.toBeEmpty();
    expect(userAgent.sipJsUserAgentConfig.contactParams["x-odoo-unique"]).toBe(
        config.contactParams["x-odoo-unique"]
    );
});

test("SIP registration retries every two seconds for sixteen seconds after a 401", async () => {
    await start();
    const voipService = await getService("voip");
    const registerer = voipService.userAgent.registerer;
    let registerCalls = 0;
    registerer.__sipJsRegisterer.register = () => registerCalls++;
    const unauthorizedResponse = {
        message: {
            reasonPhrase: "Unauthorized",
            statusCode: 401,
        },
    };

    for (let attempt = 1; attempt <= 8; attempt++) {
        registerer._onRegistrationRejected(unauthorizedResponse);
        expect(voipService.error).toBe(null);
        await advanceTime(2_000);
        expect(registerCalls).toBe(attempt);
    }

    registerer._onRegistrationRejected(unauthorizedResponse);
    expect(voipService.error.message).toInclude("login or provider details");
});

test("Dialing one of our own DIDs INVITEs the linked extension, not the DID.", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({ ...settingsData, user_id: serverState.userId });
    onRpc("voip.call", "resolve_outgoing_dial_number", ({ args }) => {
        expect.step(`resolve:${args[0]}`);
        return { number: "1000", is_internal: true };
    });
    onRpc("voip.call", "get_or_create", () => ({
        ids: [1],
        // partner_id set so the call skips the async get_contact_info fetch
        store_data: {
            "voip.call": [{ id: 1, partner_id: serverState.partnerId, phone_number: "1000" }],
        },
    }));
    await start();
    const voip = await getService("voip");
    voip.config = {
        ...voip.config,
        isInternalCallingProvisioned: true,
        usesOdooProvider: true,
        mode: "prod",
        outboundCallerId: null,
        pbxExtensionNumber: "1000",
    };
    const userAgent = voip.userAgent;
    patchWithCleanup(userAgent, {
        makeUri(number) {
            expect.step(`dial:${number}`);
            return super.makeUri(number);
        },
    });
    await userAgent.makeCall({ phone_number: "+3281234567" });
    expect.verifySteps(["resolve:+3281234567", "dial:1000"]);
});

test("canceling before the outgoing INVITE completes does not show an error", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({ ...settingsData, user_id: serverState.userId });
    const activityId = pyEnv["mail.activity"].create({
        phone: "+3281234567",
        res_id: serverState.partnerId,
        res_model: "res.partner",
    });
    onRpc("voip.call", "resolve_outgoing_dial_number", () => ({
        number: "1000",
        is_internal: true,
    }));
    const inviteDef = Promise.withResolvers();
    const sessionReadyDef = Promise.withResolvers();
    const Inviter = SIP.Inviter;
    patchWithCleanup(SIP, {
        Inviter: class extends Inviter {
            constructor(...args) {
                super(...args);
                sessionReadyDef.resolve();
            }

            invite() {
                return inviteDef.promise;
            }

            cancel() {
                inviteDef.reject(new Error("Peer connection closed."));
                return Promise.resolve();
            }
        },
    });
    await start();
    const voip = await getService("voip");
    voip.config = {
        ...voip.config,
        isInternalCallingProvisioned: true,
        usesOdooProvider: true,
        mode: "prod",
        pbxExtensionNumber: "1000",
    };
    patchWithCleanup(voip, {
        triggerError() {
            expect.step("error");
        },
    });

    const makeCallProm = voip.userAgent.makeCall({
        activity: { id: activityId },
        partner: { id: serverState.partnerId },
        phone_number: "+3281234567",
    });
    await sessionReadyDef.promise;
    await voip.userAgent.frontSession.hangup();

    expect(await makeCallProm).toBe(false);
    expect(pyEnv["voip.call"].search_count([["activity_id", "=", activityId]])).toBe(1);
    expect.verifySteps([]);
});

test("an outgoing INVITE failure still shows an error", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({ ...settingsData, user_id: serverState.userId });
    onRpc("voip.call", "resolve_outgoing_dial_number", () => ({
        number: "1000",
        is_internal: true,
    }));
    const Inviter = SIP.Inviter;
    patchWithCleanup(SIP, {
        Inviter: class extends Inviter {
            invite() {
                return Promise.reject(new Error("Peer connection closed."));
            }
        },
    });
    await start();
    const voip = await getService("voip");
    voip.config = {
        ...voip.config,
        isInternalCallingProvisioned: true,
        usesOdooProvider: true,
        mode: "prod",
        pbxExtensionNumber: "1000",
    };
    patchWithCleanup(voip, {
        triggerError() {
            expect.step("error");
        },
    });

    expect(await voip.userAgent.makeCall({ phone_number: "+3281234567" })).toBe(false);
    expect.verifySteps(["error"]);
});

test("An external call sends the automatically selected caller ID to Wazo.", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({ ...settingsData, user_id: serverState.userId });
    onRpc("voip.call", "resolve_outgoing_dial_number", () => ({
        number: "+3281234567",
        is_internal: false,
    }));
    onRpc("voip.call", "create_and_format", () => ({
        ids: [1],
        store_data: {
            "voip.call": [
                { id: 1, partner_id: serverState.partnerId, phone_number: "+3281234567" },
            ],
        },
    }));
    let inviterOptions;
    const Inviter = SIP.Inviter;
    patchWithCleanup(SIP, {
        Inviter: class extends Inviter {
            constructor(userAgent, uri, options) {
                super(userAgent, uri, options);
                inviterOptions = options;
            }
        },
    });
    await start();
    const voip = getService("voip");
    voip.config = {
        ...voip.config,
        isInternalCallingProvisioned: true,
        usesOdooProvider: true,
        mode: "prod",
        outboundCallerId: "+33122334455",
        outboundNumbers: [
            { countryId: 2, number: "+33122334455" },
            { countryId: 1, number: "+32470000001" },
        ],
        pbxAddress: "localhost",
        pbxExtensionNumber: "1000",
    };

    await voip.userAgent.makeCall({ phone_number: "+3281234567" });

    expect(inviterOptions.extraHeaders).toEqual(["X-Wazo-Selected-Caller-ID: +32470000001"]);
});

test("An external call is rejected when no active company number is configured.", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({ ...settingsData, user_id: serverState.userId });
    onRpc("voip.call", "resolve_outgoing_dial_number", () => ({
        number: "+3281234567",
        is_internal: false,
    }));
    await start();
    const voip = await getService("voip");
    voip.config = {
        ...voip.config,
        isInternalCallingProvisioned: true,
        usesOdooProvider: true,
        mode: "prod",
        outboundCallerId: null,
        pbxExtensionNumber: "1000",
    };
    patchWithCleanup(voip.userAgent.notification, {
        add(message, options) {
            expect.step(`${options.type}:${message}`);
        },
    });

    const callMade = await voip.userAgent.makeCall({ phone_number: "+3281234567" });

    expect(callMade).toBe(false);
    expect.verifySteps([
        "warning:External calls are unavailable because no active company phone number is configured.",
    ]);
});

test("An unavailable VoIP call returns the onUnavailable result.", async () => {
    await start();
    const voip = await getService("voip");
    patchWithCleanup(voip, {
        get canCall() {
            return false;
        },
    });

    const callMade = await voip.userAgent.makeCall(
        { phone_number: "+3281234567" },
        {
            onUnavailable() {
                expect.step("unavailable");
                return true;
            },
        }
    );

    expect(callMade).toBe(true);
    expect.verifySteps(["unavailable"]);
});

test("An unavailable callback replaces the external-call warning and returns its result.", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({ ...settingsData, user_id: serverState.userId });
    onRpc("voip.call", "resolve_outgoing_dial_number", () => ({
        number: "+3281234567",
        is_internal: false,
    }));
    await start();
    const voip = await getService("voip");
    voip.config = {
        ...voip.config,
        isInternalCallingProvisioned: true,
        usesOdooProvider: true,
        mode: "prod",
        outboundCallerId: null,
        pbxExtensionNumber: "1000",
    };
    patchWithCleanup(voip.userAgent.notification, {
        add() {
            expect.step("warning");
        },
    });

    const callMade = await voip.userAgent.makeCall(
        { phone_number: "+3281234567" },
        {
            onUnavailable() {
                expect.step("unavailable");
                return true;
            },
        }
    );

    expect(callMade).toBe(true);
    expect.verifySteps(["unavailable"]);
});

test("Using the fallback preserves its return value", async () => {
    await start();
    const voip = await getService("voip");
    patchWithCleanup(voip, {
        willCallUsingVoip() {
            return false;
        },
    });

    const callMade = await voip.userAgent.makeCall(
        { phone_number: "+3281234567" },
        {
            fallback() {
                expect.step("fallback");
                return false;
            },
        }
    );

    expect(callMade).toBe(false);
    expect.verifySteps(["fallback"]);
});

test("Calling through an internal device still requires a company number for an external target.", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({
        ...settingsData,
        external_device_number: "1001",
        should_call_from_another_device: false,
        user_id: serverState.userId,
    });
    onRpc("voip.call", "resolve_outgoing_dial_number", ({ args }) => {
        expect.step(`resolve:${args[0]}`);
        return {
            number: args[0],
            is_internal: args[0] === "1001",
        };
    });
    await start();
    const voip = await getService("voip");
    voip.config = {
        ...voip.config,
        isInternalCallingProvisioned: true,
        usesOdooProvider: true,
        mode: "prod",
        outboundCallerId: null,
        pbxExtensionNumber: "1000",
    };
    patchWithCleanup(voip.userAgent.notification, {
        add(message, options) {
            expect.step(`${options.type}:${message}`);
        },
    });

    await voip.userAgent.makeCall({ phone_number: "+3281234567" });

    expect.verifySteps([
        "resolve:+3281234567",
        "resolve:1001",
        "warning:External calls are unavailable because no active company phone number is configured.",
    ]);
});

test("incoming ringtone is registered before answering and unregistered on removal", async () => {
    let ringtone;
    patchWithCleanup(AudioManager.prototype, {
        registerRingtone(ringtoneToRegister) {
            ringtone = ringtoneToRegister;
            expect.step("register-ringtone");
        },
        unregisterRingtone(ringtoneToUnregister) {
            expect(ringtoneToUnregister).toBe(ringtone);
            expect.step("unregister-ringtone");
        },
    });
    await start();

    const invitation = receiveInvite({
        phone_number: "0123456789",
        sip_call_id: "test-invite-001",
    });
    expect.verifySteps(["register-ringtone"]);

    await invitation.reject();
    expect.verifySteps(["unregister-ringtone"]);
});
