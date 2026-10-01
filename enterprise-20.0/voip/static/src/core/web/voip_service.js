import { EventBus, toRaw, proxy } from "@odoo/owl";
import { UserAgent } from "@voip/core/web/user_agent";
import { CallMethodSelectionDialog } from "@voip/mobile/call_method_selection_dialog";
import { SoftphoneContainer } from "@voip/softphone/softphone_container";
import { Softphone, VOIP_PAGE_SIZE } from "@voip/softphone/softphone_model";
import { getMatchingContacts } from "@voip/utils/contact_search";
import { VoipSystrayItem } from "@voip/web/voip_systray_item";
import { loadBundle } from "@web/core/assets";
import { browser } from "@web/core/browser/browser";
import { isMobileOS } from "@web/core/browser/feature_detection";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { omit } from "@web/core/utils/objects";
import { session } from "@web/session";

/**
 * @typedef VoipConfig
 * @property {number} callActivityTypeId
 * @property {?string} didNumber
 *   The user's DID phone number in E.164 format. Null when no DID is assigned.
 * @property {?string} didNumberFormatted
 *   Localized display form of didNumber, when available.
 * @property {?("ordering"|"pending"|"active"|"suspended")} didNumberState
 *   The provisioning state of didNumber: ordering/pending numbers are still
 *   being validated by the provider, suspended numbers are locked until the
 *   account is topped up.
 * @property {?string} buyCreditsUrl
 *   IAP store URL to top up credits. Only set when the DID is suspended, so the
 *   softphone can offer a one-click "Buy Credits" link from the status menu.
 * @property {boolean} usesOdooProvider
 * @property {boolean} isInternalCallingProvisioned
 * @property {?string} mainNumber
 *   The active database-wide Default Outgoing Number in E.164 format, when available.
 * @property {?string} mainNumberFormatted
 *   Localized display form of mainNumber, when available.
 * @property {"demo" | "prod"} mode
 *   In demo mode, phone calls are simulated in the interface
 *   but no RTC sessions are actually established.
 * @property {number} missedCalls
 * @property {?string} outboundCallerId
 *   The active personal DID or Default Outgoing Number used for external calls.
 * @property {?string} outboundCallerIdFormatted
 *   Localized display form of outboundCallerId, when available.
 * @property {{ countryId: number, countryName: string, flagUrl: string, formatted: string, number: string }[]} outboundNumbers
 *   Active caller IDs assigned to the user and eligible for automatic selection.
 * @property {{ countryId: number, countryName: string, destinationType: "call_group" | "queue" | "ivr" | "call_flow", flagUrl: string, formatted: string, number: string }[]} sharedOutboundNumbers
 *   Active shared caller IDs available for manual selection.
 * @property {?string} pbxExtensionNumber
 *   The user's internal Odoo Phone extension, when provisioned.
 * @property {string} pbxAddress
 *   The address of the PBX server. Used as the hostname in SIP URIs.
 * @property {"always" | "user" | "disabled"} recordingPolicy
 * @property {string} webSocketUrl
 *   The WebSocket URL of the signaling server that will be used to
 *   communicate SIP messages between Odoo and the PBX server.
 * @property {?string} voicemailCode
 *   The phone number or short code used to dial into the voicemail system.
 */

export class Voip {
    error;
    microphoneError = null;
    isUnloading = false;
    /** @type VoipConfig */
    config;
    /** @type {Softphone} */
    softphone;
    /** @type {UserAgent} */
    userAgent;
    /** @type {EventBus} */
    bus = new EventBus();
    configRefreshId = 0;
    loadedSipBundles = new Set();
    /** Incremented to discard stale prefill results (see prefillFromActiveForm). */
    _prefillSeq = 0;
    /** Incremented when the dialer input stops belonging to the current prefill. */
    _prefillInputSeq = 0;

    constructor(env, services, config) {
        this.env = env;
        /** @type {import("@mail/core/store_service").Store} */
        this.store = services["mail.store"];
        this.dialog = services.dialog;
        this.orm = services.orm;
        this.action = services.action;
        this.busService = services.bus_service;
        this.config = config;
        this.missedCalls = this.config.missedCalls ?? 0;
        this.busService.subscribe("refresh_call_activities", () => {
            this.fetchTodayCallActivities();
        });
        this.busService.subscribe("voip.call/delete", (payload) => {
            for (const id of payload.ids) {
                this.store["voip.call"].get(id)?.delete();
            }
        });
        this.busService.subscribe("voip.call/update", (payload) => {
            const { store_data, missedCalls } = payload;
            this.store.insert(store_data);
            if (missedCalls !== undefined) {
                this.missedCalls = missedCalls;
            }
        });
        this.busService.subscribe("voip.config/updated", () => {
            this.refreshConfig();
        });
        this.busService.start();

        this.userAgent = new UserAgent(env, {
            voip: this,
            multi_tab: services["multi_tab"],
            notification: services.notification,
            bus: services.bus_service,
            orm: services.orm,
        });
        this.softphone = new Softphone(this.store, this.userAgent);
        // Re-run prefill when the form view loads a new record
        env.bus.addEventListener("VOIP:FORM_CONTROLLER:RECORD_LOADED", ({ detail }) => {
            if (this.softphone.isDisplayed) {
                this.prefillFromActiveForm(detail.resModel, detail.resId);
            }
        });
        return proxy(this);
    }

    get autoSelectCallerIdStorageKey() {
        return `voip.autoSelectCallerId.${session.db}.${user.userId}`;
    }

    get fallbackCallerIdStorageKey() {
        return `voip.fallbackCallerId.${session.db}.${user.userId}`;
    }

    /** @returns {boolean} */
    get autoSelectCallerId() {
        return browser.localStorage.getItem(this.autoSelectCallerIdStorageKey) !== "false";
    }

    /** @returns {?string} */
    get fallbackCallerId() {
        const numbers = this.callerIdNumbers;
        const storedNumber = browser.localStorage.getItem(this.fallbackCallerIdStorageKey);
        return numbers.some(({ number }) => number === storedNumber)
            ? storedNumber
            : numbers[0]?.number || null;
    }

    setAutoSelectCallerId(autoSelect) {
        browser.localStorage.setItem(this.autoSelectCallerIdStorageKey, autoSelect);
    }

    setFallbackCallerId(number) {
        if (this.callerIdNumbers.some((candidate) => candidate.number === number)) {
            browser.localStorage.setItem(this.fallbackCallerIdStorageKey, number);
        }
    }

    /** @param {number} countryId @returns {?string} */
    getOutboundCallerId(countryId) {
        if (this.autoSelectCallerId && countryId) {
            const matchingNumber = (this.config.outboundNumbers || []).find(
                (number) => number.countryId === countryId
            );
            if (matchingNumber) {
                return matchingNumber.number;
            }
        }
        return this.fallbackCallerId;
    }

    get callerIdNumbers() {
        return [
            ...(this.config.outboundNumbers || []),
            ...(this.config.sharedOutboundNumbers || []),
        ];
    }

    /**
     * Determines if `voip_secret` and `voip_username` settings are defined for
     * the current user.
     *
     * @returns {boolean}
     */
    get areCredentialsSet() {
        return Boolean(
            this.store.self_user.res_users_settings_id.voip_username &&
                this.store.self_user.res_users_settings_id.voip_secret
        );
    }

    get calls() {
        return this.store["voip.call"].records;
    }

    /** @returns {boolean} */
    get canCall() {
        if (this.config.mode === "demo") {
            return true;
        }
        return (
            this.hasRtcSupport &&
            this.isServerConfigured &&
            (this.config.usesOdooProvider
                ? this.hasInternalCallingIdentity
                : this.areCredentialsSet)
        );
    }

    /** @returns {boolean} */
    get hasEffectiveOutboundNumber() {
        return Boolean(this.config.outboundCallerId);
    }

    /** @returns {boolean} */
    get hasInternalCallingIdentity() {
        // Direct DID destinations provision a PBX user and line without creating a
        // voip.extension, so a numeric extension is not part of the SIP identity.
        return Boolean(
            this.config.usesOdooProvider &&
                this.config.isInternalCallingProvisioned &&
                this.areCredentialsSet
        );
    }

    /** @returns {boolean} */
    get isOdooPhoneProvisioning() {
        return Boolean(
            this.config.usesOdooProvider &&
                this.config.mode === "prod" &&
                this.config.didNumberState === "active" &&
                !this.hasInternalCallingIdentity
        );
    }

    /** @returns {boolean} */
    get hasPendingRequest() {
        return Boolean(this._activityRpc || this._contactRpc || this._recentCallsRpcSet?.size);
    }

    /** @returns {boolean} */
    get hasRtcSupport() {
        return Boolean(window.RTCPeerConnection && window.MediaStream && navigator.mediaDevices);
    }

    /** @returns {"available" | "demo" | "no_number" | "suspended" | "unavailable" | "waiting"} */
    get phoneHeaderState() {
        if (this.config.mode === "demo") {
            if (["ordering", "pending"].includes(this.config.didNumberState)) {
                return "waiting";
            }
            if (!this.config.didNumber && !this.hasEffectiveOutboundNumber) {
                return "no_number";
            }
            return "demo";
        }
        if (!this.config.usesOdooProvider) {
            return "available";
        }
        if (["ordering", "pending"].includes(this.config.didNumberState)) {
            return "waiting";
        }
        const hasNumber = Boolean(this.config.didNumber || this.hasEffectiveOutboundNumber);
        if (hasNumber && !this.hasInternalCallingIdentity) {
            return "unavailable";
        }
        if (this.config.didNumberState === "suspended") {
            return "suspended";
        }
        return hasNumber ? "available" : "no_number";
    }

    /** @returns {boolean} */
    get showsWaitingDidHeader() {
        return this.phoneHeaderState === "waiting";
    }

    /** @returns {boolean} */
    get showsSuspendedDidHeader() {
        return this.phoneHeaderState === "suspended";
    }

    /** @returns {boolean} */
    get showsNoNumberHeader() {
        return this.phoneHeaderState === "no_number";
    }

    /** @returns {?string} */
    get didStatusTooltip() {
        const number = this.config.outboundCallerIdFormatted || this.config.outboundCallerId;
        if (this.showsWaitingDidHeader) {
            if (this.config.mode === "demo") {
                return _t("Your number is under review. Calls remain simulated in Demo Mode.");
            }
            if (number && this.hasInternalCallingIdentity) {
                return _t(
                    "Your number is under review. Calls use %(number)s until it is approved.",
                    { number }
                );
            }
            return this.hasInternalCallingIdentity
                ? _t(
                      "Your number is under review. Internal calls remain available; external calls will be available after approval."
                  )
                : _t(
                      "Your number is under review. Internal calling is not configured; external calls also require an approved number."
                  );
        }
        if (this.showsSuspendedDidHeader) {
            if (number && this.hasInternalCallingIdentity) {
                return _t("Your number is suspended. Calls use %(number)s.", { number });
            }
            return this.hasInternalCallingIdentity
                ? _t("Your number is suspended. Internal calls remain available.")
                : _t(
                      "Your number is suspended. Internal calling is not configured, and external calls are unavailable."
                  );
        }
        if (this.showsNoNumberHeader) {
            if (this.config.mode === "demo") {
                return _t(
                    "Calls are simulated in Demo Mode. Get a number to make and receive real calls with Odoo Phone Service."
                );
            }
            if (!this.hasInternalCallingIdentity) {
                return _t(
                    "Internal and external calls are unavailable until Odoo Phone is activated and the user is configured."
                );
            }
            // Keep mentioning the extension for users provisioned through the
            // legacy extension flow, but direct PBX users do not have one.
            if (this.config.pbxExtensionNumber) {
                return _t(
                    "Internal calls are available through extension %(extension)s. An active company number is required for external calls.",
                    { extension: this.config.pbxExtensionNumber }
                );
            }
            return _t(
                "Internal calls are available. An active company number is required for external calls."
            );
        }
        if (this.phoneHeaderState === "unavailable") {
            return _t("Odoo Phone is unavailable until your user is fully configured.");
        }
        return null;
    }

    /** @returns {string} */
    get demoModeTooltip() {
        const number = this.config.outboundCallerIdFormatted || this.config.outboundCallerId;
        return number
            ? _t(
                  "Calls are simulated in Demo Mode. Switch to Odoo Phone Service to use %(number)s.",
                  { number }
              )
            : _t("Calls are simulated in Demo Mode.");
    }

    /** @returns {?string} */
    get softphoneStatusNotice() {
        if (!this.config.usesOdooProvider || this.config.mode === "demo") {
            return null;
        }
        if (this.isOdooPhoneProvisioning) {
            // To reproduce: activate the user's first number before its Odoo
            // Phone credentials and PBX line finish provisioning.
            return _t(
                "Your number is active. Your phone setup is still being finalized. Calling will be available once setup is complete."
            );
        }
        if (this.config.didNumberState === "active") {
            return null;
        }
        if (!this.hasInternalCallingIdentity) {
            if (this.showsWaitingDidHeader) {
                // To reproduce: buy the user's first number and reopen the
                // softphone before their Odoo Phone line finishes provisioning.
                return _t(
                    "Your number has been ordered and is under review. We'll notify you when it's ready."
                );
            }
            return null;
        }
        const outboundNumber =
            this.config.outboundCallerIdFormatted || this.config.outboundCallerId;
        if (this.showsWaitingDidHeader) {
            if (outboundNumber) {
                // To reproduce: set an active number as the Default Outgoing
                // Number, then buy the current user a personal number that
                // requires review.
                return _t("Calls use %(number)s while your number is under review.", {
                    number: outboundNumber,
                });
            }
            // To reproduce: with no Default Outgoing Number, buy a number that
            // requires review for a user who already has an extension.
            return _t(
                "Internal calls are available. External calls will be available once your number is approved."
            );
        }
        if (this.showsSuspendedDidHeader) {
            if (outboundNumber) {
                // To reproduce: keep an active Default Outgoing Number while
                // the current user's personal number is suspended for
                // insufficient credits.
                return _t("Calls use %(number)s until your number is reactivated.", {
                    number: outboundNumber,
                });
            }
            // To reproduce: with no Default Outgoing Number, let the current
            // user's personal number be suspended for insufficient credits.
            return _t(
                "Internal calls are available. External calls will resume once your number is reactivated."
            );
        }
        if (!outboundNumber) {
            // To reproduce: give the current user an Odoo Phone extension
            // without assigning them a personal number, and make sure there is
            // no Default Outgoing Number.
            return _t(
                "Internal calls are available. External calls require an active phone number."
            );
        }
        return null;
    }

    /** @returns {boolean} */
    get showsDemoModeHeader() {
        return this.phoneHeaderState === "demo";
    }

    /**
     * Determines if `pbxAddress` and `webSocketUrl` have been provided.
     *
     * @returns {boolean}
     */
    get isServerConfigured() {
        return Boolean(this.config.pbxAddress && this.config.webSocketUrl);
    }

    get sipBundle() {
        return this.config.mode === "prod" ? "voip.assets_sip_prod" : "voip.assets_sip_demo";
    }

    async refreshConfig() {
        const refreshId = ++this.configRefreshId;
        try {
            const { voipConfig, settings } = await this.orm.call(
                "res.users",
                "get_current_voip_config"
            );
            if (refreshId !== this.configRefreshId) {
                return;
            }
            this.config = voipConfig;
            if (settings) {
                this.store.self_user.res_users_settings_id.update(settings);
            }
            await this.startUserAgent(refreshId);
            if (refreshId !== this.configRefreshId) {
                return;
            }
            this.bus.trigger("config_changed");
            this.bus.trigger("session_changed");
        } catch (error) {
            if (refreshId !== this.configRefreshId) {
                return;
            }
            this.triggerError({
                technical: _t("Failed to refresh the VoIP configuration:"),
                technicalExtra: error.message,
            });
        }
    }

    async startUserAgent(refreshId = this.configRefreshId) {
        if (!this.canCall) {
            await this.userAgent.stop();
            // The configuration may have changed while the user agent was
            // stopping. A newer refresh is responsible for starting it with the
            // new configuration.
            if (refreshId === this.configRefreshId && !this.canCall) {
                this.showConfigError();
            }
            return;
        }
        this.triggerError({
            technical: _t("Loading SIP.js library..."),
        });
        try {
            if (!this.loadedSipBundles.has(this.sipBundle)) {
                await loadBundle(this.sipBundle);
                this.loadedSipBundles.add(this.sipBundle);
            }
            this.resolveError();
            await this.userAgent.init();
        } catch (error) {
            this.triggerError({
                technical: _t("Failed to load the SIP.js library:"),
                technicalExtra: error.message,
            });
        }
    }

    showConfigError() {
        if (!this.hasRtcSupport) {
            this.triggerError({
                message: _t(
                    "Your browser does not support some of the features required. Please try updating your browser or using a different one."
                ),
                technical: _t("RTC support is required for VoIP to work."),
            });
        } else if (!this.isServerConfigured) {
            this.triggerError({
                technical: _t("PBX or WebSocket address is missing. Please check your settings."),
            });
        } else if (
            this.isOdooPhoneProvisioning ||
            this.showsWaitingDidHeader ||
            this.showsSuspendedDidHeader ||
            this.showsNoNumberHeader
        ) {
            this.resolveError();
        } else {
            this.triggerError({
                message: _t(
                    "Your login details to use the phone are not set in your user preferences. Please check or ask your administrator if needed."
                ),
            });
        }
    }

    _fetchContactInfoIfMissing(call) {
        if (!call || call.partner_id) {
            return call;
        }
        // This is done afterwards and not awaited: it is a "costly" operation
        // that we do not want delaying the rest.
        this.orm.call("voip.call", "get_contact_info", [[call.id]]).then((data) => {
            if (data) {
                this.store.insert(data);
            }
        });
        return call;
    }

    /**
     * Creates the VOIP call record for an outgoing call, or joins the one the
     * PBX webhooks already created for the same INVITE, and updates the local
     * store with formatted data.
     * @param {Object} data
     * @param {import{"models"}.MailActivity} [data.activity]
     * @param {string} [data.alias]
     * @param {import{"models"}.ResPartner} [data.partner]
     * @param {string} data.phone_number
     * @param {string} [data.sip_call_id] Call-ID of the INVITE, correlating this
     *   record with the caller leg the PBX reports.
     * @returns {Promise<import("models").Call>}
     */
    async createCall(data) {
        const createData = omit(data, "activity", "partner", "alias");
        createData.partner_id = data.partner?.id;
        createData.activity_id = data.activity?.id;
        createData.is_production = this.config.mode === "prod";
        createData.direction = "outgoing";
        const {
            ids: [id],
            store_data,
        } = await this.orm.call("voip.call", "get_or_create", [createData]);
        this.store.insert(store_data);
        const call = this.store["voip.call"].insert(id);
        return this._fetchContactInfoIfMissing(call);
    }

    /**
     * Resolve a number to dial and classify whether it stays inside the PBX.
     * @param {string} phoneNumber
     * @returns {Promise<{number: string, is_internal: boolean}>}
     */
    resolveDialNumber(phoneNumber) {
        return this.orm.call("voip.call", "resolve_outgoing_dial_number", [phoneNumber]);
    }

    async getCallById(callId) {
        const result = await this.orm.call("voip.call", "get_by_id", [callId]);
        if (!result) {
            return null;
        }
        this.store.insert(result.store_data);
        const call = this.store["voip.call"].insert(result.ids[0]);
        return this._fetchContactInfoIfMissing(call);
    }

    async getOrCreateCall(data) {
        const { ids, store_data } = await this.orm.call("voip.call", "get_or_create", [data]);
        this.store.insert(store_data);
        const call = this.store["voip.call"].insert(ids[0]);
        return this._fetchContactInfoIfMissing(call);
    }

    async fetchContacts({
        searchTerms = "",
        loadMore = false,
        limit = VOIP_PAGE_SIZE,
        internalUsersFirst = false,
        prioritizedContactsLimit = 0,
    } = {}) {
        searchTerms = searchTerms.trim();
        // FIXME This offset is still inferred from the global Store. Matching
        // contacts may have been loaded by another search or feature, and
        // client matching may differ from the server domain, causing skipped or
        // duplicated records. Server-side insertions, deletions and reordering
        // also make offset pagination unstable.
        const offset = loadMore
            ? getMatchingContacts(this.softphone.contacts, searchTerms).length
            : 0;
        if (this._contactRpc) {
            if (offset) {
                // The initial search page is still loading; do not abort it for
                // a pagination fetch.
                return [];
            }
            this._contactRpc.abort();
        }
        this._contactRpc = this.orm.call("res.partner", "get_contacts", [], {
            offset,
            limit,
            search_terms: searchTerms,
            internal_users_first: internalUsersFirst,
            prioritized_contacts_limit: prioritizedContactsLimit,
        });
        try {
            const data = await this._contactRpc;
            this.store.insert(data.store_data || data);
            this._contactRpc = null;
            return data.prioritized_contact_ids || [];
        } catch (error) {
            if (error.event?.type === "abort") {
                error.event.preventDefault();
                return [];
            }
            if (error.message?.toLowerCase().includes("abort")) {
                // Unreliable, message content varies between browsers.
                return [];
            }
            this._contactRpc = null;
            // Don't throw, it could still be an abort error that wasn't caught
            // by the conditions above.
            console.error(error);
            return [];
        }
    }

    /** @returns {Promise<number[]>} ids of recent calls */
    async fetchRecentCalls({ offset = 0, limit = VOIP_PAGE_SIZE, direction, partnerId } = {}) {
        this._recentCallsRpcSet ||= new Set();
        const recentCallsRpc = this.orm.call("voip.call", "get_recent_phone_calls", [], {
            offset,
            limit,
            direction,
            partner_id: partnerId,
        });
        this._recentCallsRpcSet.add(recentCallsRpc);
        const { ids, store_data } = await recentCallsRpc;
        this.store.insert(store_data);
        this._recentCallsRpcSet.delete(recentCallsRpc);
        return ids;
    }

    async fetchTodayCallActivities() {
        if (this._activityRpc) {
            return;
        }
        this._activityRpc = this.orm.call("mail.activity", "get_today_call_activities");
        try {
            const data = await this._activityRpc;
            this.store.insert(data);
        } finally {
            this._activityRpc = null;
        }
    }

    resetMissedCalls() {
        if (this.missedCalls !== 0) {
            this.orm.call("res.users", "reset_last_seen_phone_call");
        }
        this.missedCalls = 0;
    }

    /**
     * Invalidates any in-flight form prefill request.
     *
     * @param {Object} [options]
     * @param {boolean} [options.clearContext=true]
     */
    invalidatePrefill({ clearContext = true } = {}) {
        this._prefillSeq++;
        if (clearContext) {
            this._prefillInputSeq++;
            this.softphone.dialer.prefillContext = null;
        }
    }

    async prefillFromActiveForm(resModel, resId) {
        // Skip while any call is in progress (ongoing or ringing)
        if (this.userAgent.frontSession) {
            return;
        }
        // Fallback: when called without params (toggle), read from active controller
        if (!resModel || !resId) {
            const controller = this.action.currentController;
            if (controller?.props?.type !== "form" || !controller?.currentState?.resId) {
                this.invalidatePrefill();
                return;
            }
            resModel = controller.props.resModel;
            resId = controller.currentState.resId;
        }
        // Skip if the same record is already pre-filled (avoids duplicate RPCs)
        const { resModel: prevModel, resId: prevId } = this.softphone.dialer.prefillContext || {};
        if (prevModel === resModel && prevId === resId) {
            return;
        }
        // Clear previous prefill state before fetching new data
        this.softphone.dialer.input.value = "";
        this.invalidatePrefill();
        const seq = this._prefillSeq;
        try {
            const { partner_id, phone, store_data } = await this.orm.call(
                "voip.call",
                "get_prefill_data",
                [resModel, resId]
            );
            // Discard the result if the prefill was superseded or is no longer
            // valid: a newer request started, the record changed, the user left
            // the form view, or typed in the dialer while the RPC was in flight.
            const controller = this.action.currentController;
            if (
                seq !== this._prefillSeq ||
                controller?.props?.type !== "form" ||
                controller?.props?.resModel !== resModel ||
                controller?.currentState?.resId !== resId ||
                this.softphone.dialer.input.value
            ) {
                return;
            }
            if (!phone) {
                return;
            }
            this.store.insert(store_data);
            Object.assign(this.softphone.dialer.input, {
                country: null,
                isValid: false,
                value: phone,
            });
            this.softphone.dialer.input.selection = {
                start: phone.length,
                end: phone.length,
                direction: "none",
            };
            this.softphone.dialer.input.focus = true;
            this.softphone.activeTab = "dialer";
            this.softphone.dialer.prefillContext = { resModel, resId };
            if (partner_id) {
                this.softphone.dialer.prefillContext.partnerId = partner_id;
            }
        } catch (error) {
            if (error?.exceptionName === "odoo.exceptions.AccessError") {
                return;
            }
            throw error;
        }
    }

    /**
     * Hides any error shown with `triggerError`. Beware that if the "delay"
     * option of the `triggerError` call was used, calling `resolveError` early
     * will not prevent the error from being shown when the delay elapses.
     * Prefer using the function returned by `triggerError` in that case (and in
     * any case really).
     */
    resolveError() {
        this.error = null;
    }

    /**
     * Triggers an error that will be displayed in the softphone, and blocks the
     * UI by default.
     *
     * @param {Object} [options={}]
     * @param {boolean} [options.isBlocking=true] True if it should block the UI
     * @param {boolean} [options.isConnecting=false] True for the transient SIP connection state
     * @param {string} [options.message] The error message to be displayed.
     * @param {string} [options.technical] Sub-message, collapse, bold
     * @param {string} [options.technicalExtra] Sub-message, collapse, not-bold
     * @param {number} [options.delay] A potential delay before showing the
     *  error. The returned function allows to both resolve the error or cancel
     *  showing it after that delay.
     * @returns {Function} A function that can be used to resolve the error or
     *  cancel showing it if a delay was provided. Also it only allows resolving
     *  the error if the error that is displayed is the one that was triggered
     *  by the original call to triggerError (compared to `resolveError` of the
     *  service which resolves any displayed error).
     */
    triggerError({
        isBlocking = true,
        isConnecting = false,
        message,
        technical,
        technicalExtra,
        buyCreditsUrl,
        delay,
    } = {}) {
        const error = {
            isBlocking,
            isConnecting,
            message,
            technical,
            technicalExtra,
            buyCreditsUrl,
        };

        let timeoutId;
        if (delay === undefined) {
            this.error = error;
        } else {
            timeoutId = setTimeout(() => (this.error = error), delay);
        }

        return () => {
            clearTimeout(timeoutId);
            if (toRaw(this.error) === error) {
                this.resolveError();
            }
        };
    }

    /**
     * Checks whether the call should use VoIP or not: it might depend on the
     * device, settings, or user choice after asking.
     *
     * @returns {Promise<boolean|null>}
     * - `true`: Use VoIP call
     * - `false`: Use native phone dialer
     * - `null`: User dismissed the dialog, no action taken
     */
    async willCallUsingVoip() {
        if (!isMobileOS()) {
            return true;
        }
        const callMethod = this.store.self_user.res_users_settings_id.how_to_call_on_mobile;
        if (callMethod !== "ask") {
            return callMethod === "voip";
        }
        return new Promise((resolve) => {
            this.dialog.add(
                CallMethodSelectionDialog,
                { setVoipChoice: resolve },
                { onClose: () => resolve(null) }
            );
        });
    }
}

export const voipService = {
    dependencies: [
        "action",
        "bus_service",
        "dialog",
        "mail.store",
        "orm",
        "multi_tab",
        "notification",
    ],
    start(env, services) {
        if (!user.isInternalUser) {
            return {};
        }
        registry.category("main_components").add("voip.SoftphoneContainer", {
            Component: SoftphoneContainer,
        });
        registry.category("systray").add("voip", { Component: VoipSystrayItem });
        registry.category("actions").add("voip.open_softphone", async () => {
            if (!voip.canCall) {
                await voip.refreshConfig();
            }
            voip.softphone.show();
        });
        const config = services["mail.store"].voipConfig || {}; // FIXME: fallback exists for tests
        delete services["mail.store"].voipConfig;
        const voip = new Voip(env, services, config);

        voip.startUserAgent();
        return voip;
    },
};

registry.category("services").add("voip", voipService);
