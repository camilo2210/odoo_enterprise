import { describe, expect, test, tick } from "@odoo/hoot";
import { toRaw } from "@odoo/owl";
import { start, startServer } from "@mail/../tests/mail_test_helpers";
import { getService, onRpc, serverState } from "@web/../tests/web_test_helpers";
import { ResUsers } from "@voip/../tests/mock_server/mock_models/res_users";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { Voip } from "@voip/core/web/voip_service";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";

describe.current.tags("desktop");
setupVoipTests();

test("caller ID selection uses the first matching country and otherwise the persisted fallback", async () => {
    patchVoipConfig({
        outboundNumbers: [
            { countryId: 2, number: "+33122334455" },
            { countryId: 1, number: "+32470000001" },
            { countryId: 1, number: "+32470000002" },
        ],
    });
    await start();
    const voip = getService("voip");

    voip.setFallbackCallerId("+33122334455");
    expect(voip.getOutboundCallerId(1)).toBe("+32470000001");
    expect(voip.getOutboundCallerId(3)).toBe("+33122334455");

    voip.setAutoSelectCallerId(false);
    expect(browser.localStorage.getItem(voip.autoSelectCallerIdStorageKey)).toBe("false");
    expect(voip.getOutboundCallerId(1)).toBe("+33122334455");
});

test("fetchContacts offsets load-more requests by matching loaded contacts", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "AAA 1", phone: "+1-555-0001" },
        { name: "AAA 2", phone: "+1-555-0002" },
        { name: "BBB 1", phone: "+1-555-0003" },
        { name: "BBB 2", phone: "+1-555-0004" },
        { name: "BBB 3", phone: "+1-555-0005" },
    ]);
    const offsets = [];
    onRpc("res.partner", "get_contacts", (args) => {
        offsets.push([args.kwargs.search_terms, args.kwargs.offset]);
    });
    await start();
    const voipService = await getService("voip");

    await voipService.fetchContacts({ searchTerms: "AAA" });
    await voipService.fetchContacts({ searchTerms: "BBB" });
    await voipService.fetchContacts({ searchTerms: "BBB", loadMore: true });

    expect(offsets).toEqual([
        ["AAA", 0],
        ["BBB", 0],
        ["BBB", 3],
    ]);
});

test("“hasValidExternalDeviceNumber” is true when an external device number is configured.", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users.settings"].create({
        external_device_number: "+247-555-183-184",
        user_id: serverState.userId,
    });
    await start();
    const voipService = await getService("voip");
    expect(voipService.userAgent.hasValidExternalDeviceNumber).toBe(true);
});

test("“hasValidExternalDeviceNumber” is false when no external device number is configured.", async () => {
    await start();
    const voipService = await getService("voip");
    expect(voipService.userAgent.hasValidExternalDeviceNumber).toBe(false);
});

function patchVoipConfig(overrides) {
    const initStoreData = ResUsers.prototype._init_store_data;
    patch(ResUsers.prototype, {
        _init_store_data(store) {
            initStoreData.call(this, store);
            store.add_global_values({
                voipConfig: {
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
                },
            });
        },
    });
    patch(Voip.prototype, {
        get hasRtcSupport() {
            return true;
        },
    });
}

test("a pending Odoo number can call using the Default Outgoing Number", async () => {
    patchVoipConfig({ didNumberState: "pending" });
    await start();
    const voipService = await getService("voip");
    voipService.store.self_user.res_users_settings_id.voip_username = "wazo_user";
    voipService.store.self_user.res_users_settings_id.voip_secret = "secret";

    expect(voipService.canCall).toBe(true);
    expect(voipService.phoneHeaderState).toBe("waiting");
    expect(voipService.showsWaitingDidHeader).toBe(true);
    expect(voipService.softphoneStatusNotice).toBe(
        "Calls use +32 87 00 00 11 while your number is under review."
    );
    expect(voipService.didStatusTooltip).toBe(
        "Your number is under review. Calls use +32 87 00 00 11 until it is approved."
    );
});

test("an ordering Odoo number waits for review without login details", async () => {
    patchVoipConfig({ didNumberState: "ordering", isInternalCallingProvisioned: false });
    await start();
    const voipService = await getService("voip");

    expect(voipService.canCall).toBe(false);
    expect(voipService.phoneHeaderState).toBe("waiting");
    expect(voipService.showsWaitingDidHeader).toBe(true);
    expect(voipService.softphoneStatusNotice).toBe(
        "Your number has been ordered and is under review. We'll notify you when it's ready."
    );
    voipService.showConfigError();
    expect(voipService.error).toBe(null);
});

test("an active Odoo number allows calls", async () => {
    patchVoipConfig({
        didNumberState: "active",
        outboundCallerId: "+3287000099",
        outboundCallerIdFormatted: "+32 87 00 00 99",
    });
    await start();
    const voipService = await getService("voip");
    voipService.store.self_user.res_users_settings_id.voip_username = "wazo_user";
    voipService.store.self_user.res_users_settings_id.voip_secret = "secret";

    expect(voipService.canCall).toBe(true);
    expect(voipService.phoneHeaderState).toBe("available");
    expect(voipService.softphoneStatusNotice).toBe(null);
});

test("a newer config refresh invalidates a pending configuration error", async () => {
    patchVoipConfig({ didNumberState: "pending", isInternalCallingProvisioned: false });
    await start();
    const voipService = await getService("voip");
    const stopDef = Promise.withResolvers();
    const configDef = Promise.withResolvers();
    patch(voipService.userAgent, { stop: () => stopDef.promise });
    const originalOrmCall = voipService.orm.call.bind(voipService.orm);
    patch(voipService.orm, {
        call(model, method, ...args) {
            if (model === "res.users" && method === "get_current_voip_config") {
                return configDef.promise;
            }
            return originalOrmCall(model, method, ...args);
        },
    });
    voipService.config.didNumber = null;
    voipService.config.didNumberState = null;
    voipService.resolveError();

    const staleStartPromise = voipService.startUserAgent();
    const refreshPromise = voipService.refreshConfig();
    stopDef.resolve();
    await staleStartPromise;

    expect(voipService.error).toBe(null);

    configDef.resolve({
        settings: false,
        voipConfig: {
            ...voipService.config,
            didNumber: "+3287000099",
            didNumberState: "active",
        },
    });
    await refreshPromise;
});

test("refreshConfig ignores an older response that arrives last", async () => {
    patchVoipConfig({ didNumberState: "pending", isInternalCallingProvisioned: false });
    await start();
    const voipService = await getService("voip");
    const staleConfigDef = Promise.withResolvers();
    const activeConfigDef = Promise.withResolvers();
    const originalOrmCall = voipService.orm.call.bind(voipService.orm);
    const configDefs = [staleConfigDef, activeConfigDef];
    patch(voipService.orm, {
        call(model, method, ...args) {
            if (model === "res.users" && method === "get_current_voip_config") {
                return configDefs.shift().promise;
            }
            return originalOrmCall(model, method, ...args);
        },
    });
    patch(voipService, { startUserAgent: () => {} });

    const staleRefreshPromise = voipService.refreshConfig();
    const activeRefreshPromise = voipService.refreshConfig();
    activeConfigDef.resolve({
        settings: false,
        voipConfig: {
            ...voipService.config,
            didNumberState: "active",
            isInternalCallingProvisioned: false,
        },
    });
    await activeRefreshPromise;
    staleConfigDef.resolve({
        settings: false,
        voipConfig: {
            ...voipService.config,
            didNumber: null,
            didNumberState: null,
        },
    });
    await staleRefreshPromise;

    expect(voipService.config.didNumberState).toBe("active");
});

test("pending and suspended numbers without a Default Outgoing Number remain internal-only", async () => {
    patchVoipConfig({
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
    });
    await start();
    const voipService = await getService("voip");
    voipService.store.self_user.res_users_settings_id.voip_username = "wazo_user";
    voipService.store.self_user.res_users_settings_id.voip_secret = "secret";

    expect(voipService.canCall).toBe(true);
    expect(voipService.phoneHeaderState).toBe("waiting");
    expect(voipService.showsWaitingDidHeader).toBe(true);
    expect(voipService.softphoneStatusNotice).toBe(
        "Internal calls are available. External calls will be available once your number is approved."
    );

    voipService.config.didNumberState = "suspended";
    expect(voipService.phoneHeaderState).toBe("suspended");
    expect(voipService.showsSuspendedDidHeader).toBe(true);
    expect(voipService.softphoneStatusNotice).toBe(
        "Internal calls are available. External calls will resume once your number is reactivated."
    );
});

test("a suspended Odoo number can call using the Default Outgoing Number", async () => {
    patchVoipConfig({ didNumberState: "suspended", buyCreditsUrl: "https://iap.test/credit" });
    await start();
    const voipService = await getService("voip");
    voipService.store.self_user.res_users_settings_id.voip_username = "suspended_user";
    voipService.store.self_user.res_users_settings_id.voip_secret = "top secret";

    expect(voipService.areCredentialsSet).toBe(true);
    expect(voipService.canCall).toBe(true);
    expect(voipService.phoneHeaderState).toBe("suspended");
    expect(voipService.showsSuspendedDidHeader).toBe(true);
    expect(voipService.softphoneStatusNotice).toBe(
        "Calls use +32 87 00 00 11 until your number is reactivated."
    );
});

test("external calls are unavailable without an active personal or Default Outgoing Number", async () => {
    patchVoipConfig({
        didNumber: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
        pbxExtensionNumber: null,
    });
    await start();
    const voipService = await getService("voip");
    voipService.store.self_user.res_users_settings_id.voip_username = "wazo_user";
    voipService.store.self_user.res_users_settings_id.voip_secret = "secret";

    expect(voipService.canCall).toBe(true);
    expect(voipService.hasInternalCallingIdentity).toBe(true);
    expect(voipService.phoneHeaderState).toBe("no_number");
    expect(voipService.showsNoNumberHeader).toBe(true);
    expect(voipService.softphoneStatusNotice).toBe(
        "Internal calls are available. External calls require an active phone number."
    );
    expect(voipService.didStatusTooltip).toBe(
        "Internal calls are available. An active company number is required for external calls."
    );
});

test("the Default Outgoing Number is an effective number without a direct DID", async () => {
    patchVoipConfig({ didNumber: null, didNumberState: null });
    await start();
    const voipService = await getService("voip");
    voipService.store.self_user.res_users_settings_id.voip_username = "wazo_user";
    voipService.store.self_user.res_users_settings_id.voip_secret = "secret";

    expect(voipService.showsNoNumberHeader).toBe(false);
    expect(voipService.phoneHeaderState).toBe("available");
    expect(voipService.softphoneStatusNotice).toBe(null);
});

test("demo mode promotes the Odoo Phone number flow", async () => {
    patchVoipConfig({
        usesOdooProvider: false,
        mode: "demo",
        didNumber: "+3287000099",
        didNumberState: "active",
    });
    await start();
    const voipService = await getService("voip");

    expect(voipService.canCall).toBe(true);
    expect(voipService.showsWaitingDidHeader).toBe(false);
    expect(voipService.showsNoNumberHeader).toBe(false);
    expect(voipService.showsDemoModeHeader).toBe(true);
    expect(voipService.demoModeTooltip).toBe(
        "Calls are simulated in Demo Mode. Switch to Odoo Phone Service to use +32 87 00 00 11."
    );

    voipService.config.didNumberState = "pending";
    expect(voipService.showsWaitingDidHeader).toBe(true);
    expect(voipService.didStatusTooltip).toBe(
        "Your number is under review. Calls remain simulated in Demo Mode."
    );

    voipService.config.didNumber = null;
    voipService.config.didNumberState = null;
    voipService.config.outboundCallerId = null;
    voipService.config.outboundCallerIdFormatted = null;
    expect(voipService.showsNoNumberHeader).toBe(true);
    expect(voipService.didStatusTooltip).toBe(
        "Calls are simulated in Demo Mode. Get a number to make and receive real calls with Odoo Phone Service."
    );
});

test("no number and no provisioned extension disables internal calling", async () => {
    patchVoipConfig({
        didNumber: null,
        didNumberState: null,
        outboundCallerId: null,
        outboundCallerIdFormatted: null,
        isInternalCallingProvisioned: false,
        pbxExtensionNumber: null,
    });
    await start();
    const voipService = await getService("voip");
    voipService.store.self_user.res_users_settings_id.voip_username = "stale_user";
    voipService.store.self_user.res_users_settings_id.voip_secret = "stale_secret";

    expect(voipService.hasInternalCallingIdentity).toBe(false);
    expect(voipService.canCall).toBe(false);
    expect(voipService.phoneHeaderState).toBe("no_number");
    expect(voipService.showsNoNumberHeader).toBe(true);
    expect(voipService.softphoneStatusNotice).toBe(null);
});

test("Odoo Phone provisioning requires an active personal number", async () => {
    patchVoipConfig({
        didNumberState: "active",
        isInternalCallingProvisioned: false,
        pbxExtensionNumber: null,
    });
    await start();
    const voipService = await getService("voip");
    voipService.store.self_user.res_users_settings_id.voip_username = "stale_user";
    voipService.store.self_user.res_users_settings_id.voip_secret = "stale_secret";

    expect(voipService.phoneHeaderState).toBe("unavailable");
    expect(voipService.canCall).toBe(false);
    expect(voipService.isOdooPhoneProvisioning).toBe(true);
    expect(voipService.softphoneStatusNotice).toBe(
        "Your number is active. Your phone setup is still being finalized. Calling will be available once setup is complete."
    );
    expect(voipService.didStatusTooltip).toBe(
        "Odoo Phone is unavailable until your user is fully configured."
    );
    voipService.showConfigError();
    expect(voipService.error).toBe(null);

    voipService.config.isInternalCallingProvisioned = true;
    expect(voipService.isOdooPhoneProvisioning).toBe(false);
    expect(voipService.canCall).toBe(true);
    expect(voipService.phoneHeaderState).toBe("available");
    expect(voipService.softphoneStatusNotice).toBe(null);

    voipService.config.didNumber = null;
    voipService.config.didNumberState = null;
    voipService.config.isInternalCallingProvisioned = false;
    expect(voipService.isOdooPhoneProvisioning).toBe(false);
    expect(voipService.phoneHeaderState).toBe("unavailable");
    voipService.showConfigError();
    expect(voipService.error).not.toBe(null);
});

test("prefillFromActiveForm discards stale results when called concurrently", async () => {
    await start();
    const voipService = await getService("voip");

    // Intercept orm.call directly to control RPC timing without
    // the onRpc handler serialization that would block concurrent calls.
    const rawVoip = toRaw(voipService);
    const rawOrm = toRaw(rawVoip.orm);
    const rpcDefs = [];

    patch(rawOrm, {
        call(...args) {
            const [model, method] = args;
            if (model === "voip.call" && method === "get_prefill_data") {
                // 0 = Slow RPC: won't resolve until explicitly triggered
                // 1 = Fast RPC
                const index = rpcDefs.push(Promise.withResolvers()) - 1;
                return rpcDefs[index].promise;
            }
            return super.call(...args);
        },
    });

    // Override the getter-only currentController on the raw action service
    const rawAction = toRaw(rawVoip.action);
    let mockController = null;
    patch(rawAction, {
        get currentController() {
            return mockController;
        },
    });

    // Simulate being on partner 1's form view
    mockController = {
        props: { type: "form", resModel: "res.partner" },
        currentState: { resId: 1 },
    };
    voipService.prefillFromActiveForm();

    // Simulate navigating to partner 2's form view
    mockController = {
        props: { type: "form", resModel: "res.partner" },
        currentState: { resId: 2 },
    };
    const secondCall = voipService.prefillFromActiveForm();

    // Resolve the second (latest) RPC first
    rpcDefs[1].resolve({ partner_id: 2, phone: "+1-555-0002", store_data: {} });
    await secondCall;

    // Softphone should reflect partner 2
    expect(voipService.softphone.dialer.input.value).toBe("+1-555-0002");
    expect(voipService.softphone.dialer.prefillContext).toEqual({
        resModel: "res.partner",
        resId: 2,
        partnerId: 2,
    });

    // Resolve the stale first RPC
    rpcDefs[0].resolve({ partner_id: 1, phone: "+1-555-0001", store_data: {} });
    // Yield to let microtasks from the stale promise resolve
    await tick();

    // Softphone should still reflect partner 2, not overwritten by partner 1
    expect(voipService.softphone.dialer.input.value).toBe("+1-555-0002");
    expect(voipService.softphone.dialer.prefillContext).toEqual({
        resModel: "res.partner",
        resId: 2,
        partnerId: 2,
    });
});

test("invalidating a prefill discards its pending result", async () => {
    await start();
    const voipService = await getService("voip");
    const prefillDef = Promise.withResolvers();
    patch(voipService.action, {
        currentController: {
            props: { type: "form", resModel: "res.partner" },
            currentState: { resId: 1 },
        },
    });
    onRpc("voip.call", "get_prefill_data", async () => {
        await prefillDef.promise;
        return { phone: "+1-555-0001", store_data: {} };
    });

    const prefillProm = voipService.prefillFromActiveForm();
    voipService.invalidatePrefill();
    prefillDef.resolve();
    await prefillProm;

    expect(voipService.softphone.dialer.input.value).toBe("");
    expect(voipService.softphone.dialer.prefillContext).toBe(null);
});

test("hiding the softphone invalidates its prefill context", async () => {
    await start();
    const voipService = await getService("voip");
    voipService.softphone.dialer.prefillContext = {
        resModel: "res.partner",
        resId: 1,
    };
    const prefillSeq = voipService._prefillSeq;

    voipService.softphone.hide();

    expect(voipService.softphone.dialer.prefillContext).toBe(null);
    expect(voipService._prefillSeq).toBe(prefillSeq + 1);
});
