import { AudioManager } from "@voip/core/web/audio_manager";
import { Registerer } from "@voip/core/web/registerer";
import { Session } from "@voip/core/web/session";
import { isSamePhoneNumber, PhoneNumberMultiSet } from "@voip/utils/utils";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { rpc } from "@web/core/network/rpc";
import { cleanPhoneNumber, openPhoneLink } from "@web/core/phone/phone_call";
import { Reactive } from "@web/core/utils/reactive";
import { session } from "@web/session";

export class UserAgent extends Reactive {
    attemptingToReconnect = false;
    _reconnectionRetryTimeout;
    /** @type {string} */
    UUID = crypto.randomUUID();
    /**
     * Timeout (in ms) after which an agent is considered stale if no
     * heartbeat is received.
     */
    _AGENT_TIMEOUT = 120_000;
    /**
     * UUIDs of remote agents with active calls mapped to their last seen
     * timestamp. Stale entries (older than _AGENT_TIMEOUT) are removed
     * periodically.
     *
     * @type {Map<string, number>}
     */
    _remoteActiveAgentUUIDs = new Map();
    /**
     * Monotonic counter incremented on every broadcast sent by this agent.
     * Receivers use it to detect and drop reordered messages
     * (see `_onAgentState`).
     *
     * @type {number}
     */
    _broadcastSeq = 0;
    /**
     * Highest agent_state sequence number seen per sender, together with the
     * receive timestamp. Used by `_onAgentState` to drop reordered messages
     * and cleaned alongside `_remoteActiveAgentUUIDs`.
     *
     * @type {Map<string, {seq: number, lastSeenAt: number}>}
     */
    _lastAgentStateSeqs = new Map();
    /**
     * UUIDs of agents in the same device (discovered via BroadcastChannel).
     * Periodically rebuilt to clean stale entries from crashed tabs.
     *
     * @type {Set<string>}
     */
    _localAgentUUIDs = new Set();
    /** @type {PhoneNumberMultiSet} Phone numbers to ignore (e.g. during a pull) */
    _ignoredPhoneNumbers = new PhoneNumberMultiSet();
    /** @type {{id: string, targetUUID: string, pendingEntries: Object[]}|null} */
    pull = null;
    /** @type {{pullId: string, targetUUID: string, resolve?: Function}|null} */
    push = null;
    /** @type {Registerer} */
    registerer;
    /** @type {?Session} */
    frontSession = null;
    /** @type {Record<string,Session>} */
    sessions = {};
    /**
     * Maps each main session key to its transfer session key for attended
     * transfers. The main session is the one being transferred (existed first),
     * and the transfer session is the one created to consult the transfer target.
     *
     * @type {[string,string][]}
     */
    transferPairs = [];
    /** @type {import("@voip/core/web/voip_service").Voip} */
    voip;
    multiTab;
    env;
    /** @type {AudioManager} */
    audioManager;
    /** @type {import("sip.js").UserAgent} */
    __sipJsUserAgent;
    isInitialized = false;
    /**
     * Discriminator appended to the Contact URI as the `x-odoo-unique` parameter.
     *
     * Asterisk identifies a registration binding by the Contact URI alone, so
     * without a per-window difference inside the URI every window of the same
     * user collapses into a single binding and only the last one to REGISTER can
     * be rung. It has to be a URI parameter rather than part of the user part:
     * res_pjsip_path.c matches the user part against the AOR name to decide
     * whether to attach the edge's flow-token Path, and that Path is what makes
     * an inbound call routable.
     *
     * Assigned once per user agent so that reading the SIP.js configuration
     * twice cannot yield two different Contact URIs.
     *
     * @type {string}
     */
    _uniqueContactId = crypto.randomUUID();

    constructor(env, { voip, multi_tab, notification, bus, orm }) {
        super();
        this.env = env;
        this.multiTab = multi_tab;
        this.notification = notification;
        this.voip = voip;
        this.busService = bus;
        this.orm = orm;
        window.addEventListener("beforeunload", this._onBeforeUnload.bind(this));
        this._notificationBroadcastChannel = new BroadcastChannel("voip_notification_channel");
        this._notificationBroadcastChannel.addEventListener("message", ({ data }) => {
            // Service-worker clients.matchAll() can miss an already-open Odoo
            // tab when that tab is not controlled by the current service worker.
            // The BroadcastChannel gives notification actions a same-origin
            // path to the SIP user agent that is actually ringing.
            this.handleMessage(data);
        });
        this.audioManager = new AudioManager(this.voip);
        this._audioManagerProm = this.audioManager.setup();

        this._setupLocalAgentUUIDs();
    }

    _setupLocalAgentUUIDs() {
        const bc = new BroadcastChannel("voip_agents_channel");
        bc.addEventListener("message", (event) => {
            const data = event.data;
            if (data.newAgentUUID) {
                this._localAgentUUIDs.add(data.newAgentUUID);
                bc.postMessage({ oldAgentUUID: this.UUID });
            }
            if (data.oldAgentUUID) {
                this._localAgentUUIDs.add(data.oldAgentUUID);
            }
        });
        bc.postMessage({ newAgentUUID: this.UUID });
        // Periodically rebuild to clean stale entries from crashed tabs.
        setInterval(() => {
            this._localAgentUUIDs.clear();
            bc.postMessage({ newAgentUUID: this.UUID });
        }, 60_000);
    }

    /**
     * @param {BeforeUnloadEvent} ev
     * @returns {string|undefined}
     */
    _onBeforeUnload(ev) {
        if (!this._sessionCount) {
            return;
        }
        ev.preventDefault();
        return (ev.returnValue = _t(
            "There is still a call in progress, are you sure you want to leave the page?"
        ));
    }

    get _sessionCount() {
        return Object.keys(this.sessions).length;
    }

    /** @returns {Session[]} */
    get _ongoingSessions() {
        return Object.values(this.sessions).filter((s) => s.isOngoing);
    }

    /** @returns {number} */
    get _ongoingSessionCount() {
        return this._ongoingSessions.length;
    }

    _addSession(session) {
        this.sessions[session.key] = session;
        this.voip.bus.trigger("session_changed");
    }

    _createSession(params, { promote = true } = {}) {
        const session = new Session(this.voip, {
            onSessionDescriptionHandler: (...args) =>
                this._onSessionDescriptionHandler(session, ...args),
            onIncomingRingtoneRequested: () => this.requestIncomingRingtone(),
            onSessionStateEstablished: () => this._onSessionStateEstablished(session),
            onSessionStateTerminated: () => this._onSessionStateTerminated(session),
            ...params,
        });
        this.audioManager.registerRingtone(session.ringtone);
        this._addSession(session);
        if (promote) {
            this.promoteToFront(session.key);
        }
        return session;
    }

    /**
     * Promotes a session to the front, putting all other sessions on
     * hold.
     *
     * @param {string} sessionKey
     */
    promoteToFront(sessionKey) {
        const session = this.sessions[sessionKey];
        if (!session) {
            return;
        }
        for (const s of Object.values(this.sessions)) {
            if (s.key === sessionKey || s.isOnHold) {
                continue;
            }
            s.isOnHold = true;
        }
        this.frontSession = session;
        this.frontSession.isOnHold = false;
        this.voip.bus.trigger("session_changed");
    }

    _removeSession(session) {
        this.audioManager.unregisterRingtone(session.ringtone);
        delete this.sessions[session.key];
        const index = this.transferPairs.findIndex((p) => p.includes(session.key));
        if (index !== -1) {
            this.transferPairs.splice(index, 1);
        }
        if (this.frontSession?.key === session.key) {
            this.frontSession = Object.values(this.sessions).at(-1) || null;
            if (this.frontSession) {
                this.frontSession.isOnHold = false;
            }
        }
        this.voip.bus.trigger("session_changed");
    }

    /** @returns {Session|null} */
    get callInvitationSession() {
        return (
            Object.values(this.sessions)
                .reverse()
                .find((s) => s.direction === "incoming" && s.isCalling) ?? null
        );
    }

    _subscribeToTransferEvents() {
        this._subscribeBroadcast("voip/agent_state", this._onAgentState);
        this._subscribeBroadcast("voip/request_agent_states", this._onRequestAgentStates);
        this._subscribeBroadcast("voip.call.pull/initiate", this._onPullInitiate);
        this._subscribeBroadcast("voip.call.pull/suppress_invite", this._onSuppressInvite);
        this._subscribeAsPuller("voip.call.pull/pending_entries", this._onPendingEntries);
        this._subscribeAsPuller("voip.call.pull/entry_failed", this._onPullEntryFailed);
        this._subscribeAsPusher(
            "voip.call.pull/pending_entries_received",
            this._onPendingEntriesReceived
        );
        this._subscribeAsPusher("voip.call.pull/result", this._onPullResult);
    }

    /** @returns {boolean} */
    get hasTransferInProgress() {
        return Boolean(this.pull || this.push);
    }

    /**
     * @param {string} pullId
     * @returns {boolean}
     */
    _isStillPulling(pullId) {
        return this.pull?.id === pullId;
    }

    /**
     * @param {string} pullId
     * @returns {boolean}
     */
    _isStillPushing(pullId) {
        return this.push?.pullId === pullId;
    }

    /**
     * @param {{senderUUID: string, senderSeq: number, active: boolean}} param0
     */
    _onAgentState({ senderUUID, senderSeq, active }) {
        const last = this._lastAgentStateSeqs.get(senderUUID);
        if (last && senderSeq < last.seq) {
            // Reordered: the sender has already moved past this state.
            return;
        }
        const now = Date.now();
        this._lastAgentStateSeqs.set(senderUUID, { seq: senderSeq, lastSeenAt: now });
        if (active) {
            this._remoteActiveAgentUUIDs.set(senderUUID, now);
        } else {
            this._remoteActiveAgentUUIDs.delete(senderUUID);
        }
    }

    _onRequestAgentStates() {
        if (this._ongoingSessionCount > 0) {
            this._broadcast("voip/agent_state", { active: true });
        }
    }

    /**
     * Starts the heartbeat mechanism: sends periodic heartbeats when this agent
     * has active calls, and cleans up stale entries from crashed tabs.
     */
    _startAgentLivenessCheck() {
        // Send heartbeat every 60 seconds if we have ongoing calls
        setInterval(() => {
            if (this._ongoingSessionCount > 0) {
                this._broadcast("voip/agent_state", { active: true });
            }
        }, 60_000);

        // Cleanup stale entries every 60 seconds
        setInterval(() => {
            const now = Date.now();
            for (const [uuid, lastSeenAt] of this._remoteActiveAgentUUIDs) {
                if (now - lastSeenAt > this._AGENT_TIMEOUT) {
                    this._remoteActiveAgentUUIDs.delete(uuid);
                }
            }
            for (const [uuid, { lastSeenAt }] of this._lastAgentStateSeqs) {
                if (now - lastSeenAt > this._AGENT_TIMEOUT) {
                    this._lastAgentStateSeqs.delete(uuid);
                }
            }
        }, 60_000);
    }

    /**
     * @param {number} succeeded
     * @param {number} failed
     * @param {"pull"|"push"} side - "pull" for the tab that pulled calls,
     *   "push" for the source tab that gave them away.
     */
    _notifyTransferResult(succeeded, failed, side) {
        if (succeeded === 0 && failed === 0) {
            this.notification.add(_t("No calls to transfer"), {
                type: "info",
                autocloseDelay: 6000,
            });
        } else if (failed === 0) {
            this.notification.add(
                side === "pull"
                    ? succeeded === 1
                        ? _t("Switched 1 call to this tab")
                        : _t("Switched %(succeeded)s calls to this tab", { succeeded })
                    : succeeded === 1
                    ? _t("Transferred 1 call to the other tab")
                    : _t("Transferred %(succeeded)s calls to the other tab", { succeeded }),
                { type: "success", autocloseDelay: 6000 }
            );
        } else if (succeeded === 0) {
            this.notification.add(
                failed === 1
                    ? _t("Failed to transfer 1 call")
                    : _t("Failed to transfer %(failed)s calls", { failed }),
                { type: "warning", autocloseDelay: 6000 }
            );
        } else {
            this.notification.add(
                side === "pull"
                    ? _t("Switched %(succeeded)s call(s), %(failed)s failed", { succeeded, failed })
                    : _t("Transferred %(succeeded)s call(s), %(failed)s failed", {
                          succeeded,
                          failed,
                      }),
                { type: "warning", autocloseDelay: 6000 }
            );
        }
    }

    /** @returns {boolean} */
    get hasCallInvitation() {
        return this.callInvitationSession !== null;
    }

    /** @returns {boolean} */
    get hasRemoteActiveCalls() {
        return Array.from(this._remoteActiveAgentUUIDs.keys()).some(
            (uuid) => !this._localAgentUUIDs.has(uuid)
        );
    }

    /** @returns {string|null} */
    get lastNonLocalActiveUserAgentUUID() {
        return (
            Array.from(this._remoteActiveAgentUUIDs.keys()).findLast(
                (uuid) => !this._localAgentUUIDs.has(uuid)
            ) ?? null
        );
    }

    /** @returns {boolean} */
    get hasValidExternalDeviceNumber() {
        if (!this.voip.store.self_user.res_users_settings_id.external_device_number) {
            return false;
        }
        return (
            cleanPhoneNumber(
                this.voip.store.self_user.res_users_settings_id.external_device_number
            ) !== ""
        );
    }

    /** @returns {boolean} */
    get willCallFromAnotherDevice() {
        return this.hasValidExternalDeviceNumber;
    }

    /** @returns {import("sip.js").URI} */
    get uri() {
        return SIP.UserAgent.makeURI(
            `sip:${this.voip.store.self_user.res_users_settings_id.voip_username}@${this.voip.config.pbxAddress}`
        );
    }

    /** @returns {import("sip.js").UserAgentOptions} */
    get sipJsUserAgentConfig() {
        const isDebug = odoo.debug !== "";
        return {
            authorizationPassword: this.voip.store.self_user.res_users_settings_id.voip_secret,
            authorizationUsername: this.voip.store.self_user.res_users_settings_id.voip_username,
            delegate: {
                onDisconnect: (error) => this._onTransportDisconnected(error),
                onInvite: (inviteSession) => this._onIncomingInvitation(inviteSession),
            },
            ...(this.voip.config.usesOdooProvider
                ? {
                      contactName: this.voip.store.self_user.res_users_settings_id.voip_username,
                      contactParams: {
                          transport: "ws",
                          "x-odoo-unique": this._uniqueContactId,
                      },
                      viaHost: this.voip.config.pbxAddress,
                  }
                : { hackIpInContact: true }),
            logBuiltinEnabled: isDebug,
            logLevel: isDebug ? "debug" : "error",
            sessionDescriptionHandlerFactory: SIP.Web.defaultSessionDescriptionHandlerFactory(
                this.audioManager.requestMediaStreamForSIP.bind(this.audioManager)
            ),
            sessionDescriptionHandlerFactoryOptions: { iceGatheringTimeout: 1000 },
            sipExtension100rel: SIP.SIPExtension.Supported,
            transportOptions: {
                keepAliveInterval: 20,
                server: this.voip.config.webSocketUrl,
                traceSip: isDebug,
            },
            uri: this.uri,
            userAgentString: `Odoo ${session.server_version} SIP.js/${SIP.version}`,
        };
    }

    get isInDoNotDisturbMode() {
        const dndUntil = this.voip.store.self_user.res_users_settings_id.do_not_disturb_until_dt;
        return Boolean(dndUntil) && dndUntil > luxon.DateTime.now();
    }

    async attemptReconnection(attemptCount = 0) {
        if (this.voip.isUnloading) {
            // Do not try to reconnect if the page is being naturally unloaded.
            // Note that this also allows to not show the "attempting to
            // reconnect" error message each time the page is being unloaded.
            return;
        }
        if (attemptCount > 5) {
            this.voip.triggerError({
                message: _t("Connection lost. Please ask your administrator for help."),
                technical: _t("The WebSocket connection was lost and couldn't be reestablished."),
            });
            return;
        }

        if (this.attemptingToReconnect) {
            return;
        }
        clearTimeout(this._reconnectionRetryTimeout);
        this._reconnectionRetryTimeout = undefined;
        this.attemptingToReconnect = true;
        const resolveWSError = this.voip.triggerError({
            message: _t("Connection lost. Attempting to reestablish the connection…"),
            technical: _t("There seems to be an issue with the WebSocket connection."),
        });
        try {
            await this.__sipJsUserAgent.reconnect();
            await this.registerer.register();
            resolveWSError();
        } catch {
            this._reconnectionRetryTimeout = setTimeout(
                () => this.attemptReconnection(attemptCount + 1),
                2 ** attemptCount * 1000 + Math.random() * 500
            );
        } finally {
            this.attemptingToReconnect = false;
        }
    }

    async init() {
        if (!this.isInitialized) {
            this._subscribeToTransferEvents();
            this._broadcast("voip/request_agent_states");
            this._startAgentLivenessCheck();
            this._shouldAnswerToControlHandles = new Set();
            this._shouldDeclineToControlHandles = new Set();
            this.voip.bus.addEventListener("registerer_changed", () => {
                if (this.pendingAction && this.registerer?.isRegistered) {
                    this.executeAction(this.pendingAction);
                }
                delete this.pendingAction;
            });
            navigator.serviceWorker?.addEventListener("message", ({ data }) =>
                this.handleMessage(data)
            );
            navigator.serviceWorker?.controller?.postMessage("VOIP:USER_AGENT_IS_LISTENING");
            // Notification clicks can open a cold Odoo tab. Ask the service
            // worker for any click action it buffered while this user agent was
            // loading assets and registering its SIP endpoint.
            this._notificationBroadcastChannel.postMessage({
                type: "VOIP:GET_PENDING_NOTIFICATION_ACTIONS",
            });
            this.isInitialized = true;
        }
        return this.restart();
    }

    async restart() {
        if (this._sessionCount) {
            return;
        }
        await this.stop();
        try {
            this.__sipJsUserAgent = new SIP.UserAgent(this.sipJsUserAgentConfig);
        } catch (error) {
            this.voip.triggerError({
                technical: _t("An error occurred during the instantiation of the user agent:"),
                technicalExtra: error.message,
            });
            return;
        }
        this.voip.triggerError({ isConnecting: true, message: _t("Connecting…") });
        try {
            await this.__sipJsUserAgent.start();
        } catch {
            this.voip.triggerError({
                technical: _t(
                    "The user agent could not be started. The WebSocket server URL may be incorrect. Check the WebSocket server URL in the VoIP Provider Settings."
                ),
            });
            return;
        }

        this.registerer = new Registerer(this.voip, this.__sipJsUserAgent);
        await this.registerer.register();

        await this._audioManagerProm;
    }

    async stop() {
        if (this.registerer) {
            try {
                await this.registerer.destroy();
            } catch {
                // The agent may already be disconnected.
            }
            this.registerer = undefined;
        }
        if (this.__sipJsUserAgent) {
            try {
                await this.__sipJsUserAgent.stop();
            } catch {
                // The agent may already be stopped.
            }
            this.__sipJsUserAgent = undefined;
        }
    }

    isInProgress(call) {
        const { id: callId, state } = call;
        const sessions = Object.values(this.sessions);
        if (sessions.some((s) => s.call?.id === callId && s.isInProgress)) {
            return true;
        }
        // The call might be "in progress" on another device or even belong to
        // another user. For those, we consider them "in progress" only if they
        // are not suspiciously old, which could indicate a missed status
        // update. See SUSPICIOUS_OLD_IN_PROGRESS_CALLS.
        const now = luxon.DateTime.now();
        const getDateTime = (value) =>
            typeof value === "string" ? deserializeDateTime(value) : value;
        if (state === "calling") {
            return getDateTime(call.create_date) >= now.minus({ minutes: 5 });
        }
        if (state === "ongoing") {
            return getDateTime(call.start_date || call.create_date) >= now.minus({ hours: 4 });
        }
        return false;
    }

    handleMessage(data) {
        if (data?.type === "VOIP:IS_USER_AGENT_LISTENING?") {
            navigator.serviceWorker?.controller?.postMessage("VOIP:USER_AGENT_IS_LISTENING");
            return;
        }
        if (data?.type === "VOIP:CALL_NOTIFICATION_CLICK") {
            if (this.registerer?.isRegistered) {
                this.executeAction(data);
                delete this.pendingAction;
            } else {
                this.pendingAction = data;
            }
        }
    }

    _findSessionForNotification(data) {
        const sessions = Object.values(this.sessions);
        const matches = (session) =>
            session.call?.id === data.res_id ||
            (data.control_handle && session.controlHandle === data.control_handle);
        // Prefer a still-ringing session: a queue/group can re-ring the same
        // conversation, and a stale terminated match returned first would drop
        // the click, since executeAction only acts on an isCalling session.
        return (
            sessions.find((session) => matches(session) && session.isCalling) ||
            sessions.find(matches)
        );
    }

    async executeAction(data) {
        switch (data.action) {
            case "VOIP:CALL_BACK_MISSED_CALL":
                this.makeCall({ phone_number: data.call_phone_number });
                break;
            case "VOIP:ANSWER_INCOMING_CALL": {
                const session = this._findSessionForNotification(data);
                if (session?.isCalling) {
                    session.accept();
                } else if (!session) {
                    // If the INVITE is not in this tab yet, remember the control
                    // handle. The first webhook can notify before this browser's
                    // own leg exists, so it is the stable key until the
                    // Invitation arrives and self-selects.
                    this._shouldAnswerToControlHandles.add(data.control_handle);
                }
                break;
            }
            case "VOIP:DECLINE_INCOMING_CALL": {
                const session = this._findSessionForNotification(data);
                if (session?.isCalling) {
                    await session.hangup();
                } else if (!session) {
                    // The click can land before SIP.js emits the Invitation.
                    // Remember the control handle so the future Invitation is
                    // rejected the moment it arrives.
                    this._shouldDeclineToControlHandles.add(data.control_handle);
                }
                break;
            }
            default: {
                if (data.call_state === "calling") {
                    const session = this._findSessionForNotification(data);
                    if (session?.isCalling) {
                        return;
                    }
                }
                if (this._sessionCount) {
                    return;
                }
                this.voip.softphone.activeTab = "recent";
                this.voip.resetMissedCalls();
                this.voip.softphone.show();
            }
        }
    }

    /**
     * Returns true if the given session is part of an attended transfer pair,
     * either as the main session or as the transfer session.
     *
     * @param {string} sessionKey
     * @returns {boolean}
     */
    isInTransferPair(sessionKey) {
        return this.transferPairs.some((p) => p.includes(sessionKey));
    }

    /**
     * Performs a "blind transfer", i.e., instructs the remote party to connect
     * to the given "transferTarget" by sending a REFER request. It is called
     * "blind" because, once the REFER request has been accepted, the call is
     * immediately terminated regardless of whether the transfer succeeded.
     *
     * @param {string} sessionKey - The key of the session to transfer.
     * @param {string} transferTarget
     */
    blindTransfer(sessionKey, transferTarget) {
        const session = this.sessions[sessionKey];
        if (!session?.isOngoing) {
            return;
        }
        session.refer(this.makeUri(transferTarget), {
            requestDelegate: {
                onAccept: () => session.hangup(),
            },
        });
        this.voip.softphone.inCallView.activeView = "default";
    }

    /**
     * @param {Object} data
     * @param {string} data.phone_number - The phone number to call.
     * @param {string} [data.alias] - An optional alias to display for the call, e.g., `Mailbox`.
     * @param {Object} [options={}]
     * @param {Function|null} [options.fallback=null]
     *  Called when the user chooses to call with their device rather than Odoo
     *  Phone. Returns whether a call was initiated.
     * @param {Function|null} [options.onUnavailable=null] - Called instead of the default warning
     *   when the selected VoIP route cannot place the call. Returns whether a fallback call was
     *   initiated.
     * @param {Function|null} [options.onCallRecordCreationStarted=null] - Called when creation of
     *   the server-side call record has started.
     * @param {string|null} [options.transferFromSessionKey=null] - The key of the session being
     *   transferred (attended transfer). When provided, the new session will be paired with it.
     * @returns {Promise<boolean>} Whether a call was initiated.
     */
    async makeCall(
        data,
        {
            fallback = null,
            onUnavailable = null,
            onCallRecordCreationStarted = null,
            transferFromSessionKey = null,
        } = {}
    ) {
        this.voip.softphone.clearActiveRecord();
        const useVoip = await this.voip.willCallUsingVoip();
        if (useVoip === null) {
            return false; // User dismissed the dialog, do nothing
        }
        if (!useVoip) {
            if (fallback) {
                return fallback();
            }
            openPhoneLink(data.phone_number);
            return true;
        }
        // canCall being false means the SIP stack was never loaded.
        if (!this.voip.canCall) {
            return onUnavailable ? onUnavailable() : false;
        }
        if (transferFromSessionKey && !this.sessions[transferFromSessionKey]) {
            console.error("No call to transfer.");
            return false;
        }
        const createDate = luxon.DateTime.now();
        const willCallFromAnotherDevice = this.willCallFromAnotherDevice;
        let target = { number: data.phone_number, is_internal: false };
        if (this.voip.config.usesOdooProvider) {
            // Dialing one of our own DIDs would loop out the trunk and back.
            try {
                target = await this.voip.resolveDialNumber(data.phone_number);
            } catch (error) {
                console.warn("Dial-number resolution failed; dialing the number as-is.", error);
            }
        }
        data = { ...data, phone_number: target.number };

        let phoneNumber = target.number;
        let isInternal = target.is_internal;
        if (willCallFromAnotherDevice && this.voip.config.usesOdooProvider) {
            const deviceNumber =
                this.voip.store.self_user.res_users_settings_id.external_device_number;
            let device = { number: deviceNumber, is_internal: false };
            try {
                device = await this.voip.resolveDialNumber(deviceNumber);
            } catch (error) {
                console.warn("Device-number resolution failed; dialing the number as-is.", error);
            }
            phoneNumber = device.number;
            isInternal = isInternal && device.is_internal;
        } else if (willCallFromAnotherDevice) {
            phoneNumber = this.voip.store.self_user.res_users_settings_id.external_device_number;
        }

        if (
            this.voip.config.usesOdooProvider &&
            this.voip.config.mode === "prod" &&
            !isInternal &&
            !this.voip.config.outboundCallerId
        ) {
            if (onUnavailable) {
                return onUnavailable();
            }
            this.notification.add(
                _t(
                    "External calls are unavailable because no active company phone number is configured."
                ),
                { type: "warning" }
            );
            return false;
        }

        let inviterSession = null;
        let outboundNumber = null;
        try {
            const inviterOptions = { earlyMedia: true };
            // Wazo selects the authorized caller ID from its dedicated header.
            if (this.voip.config.usesOdooProvider && !isInternal) {
                let countryId;
                try {
                    ({ countryId } = await rpc("/voip/parse_phone_number", {
                        data: { phone_number: target.number },
                    }));
                } catch (error) {
                    console.warn(
                        "Phone-country detection failed; using the fallback caller ID.",
                        error
                    );
                }
                const callerId = this.voip.getOutboundCallerId(countryId);
                if (callerId) {
                    outboundNumber = this.voip.callerIdNumbers.find(
                        ({ number }) => number === callerId
                    );
                    inviterOptions.extraHeaders = [`X-Wazo-Selected-Caller-ID: ${callerId}`];
                }
            }
            inviterSession = new SIP.Inviter(
                this.__sipJsUserAgent,
                this.makeUri(phoneNumber),
                inviterOptions
            );
        } catch (error) {
            console.error(error);
            this.voip.triggerError({
                technical: _t(
                    "Failed to create a SIP Inviter for the following number: %(phoneNumber)s",
                    { phoneNumber }
                ),
                technicalExtra: error.message,
            });
            return false;
        }
        // SIP.js builds the INVITE in the Inviter constructor, so its Call-ID is
        // known before the request is sent. The PBX reports that same value as
        // `sip_call_id` on the caller leg it webhooks back, so sending it now is
        // what makes this record and those webhooks one call instead of two.
        const callProm = this.voip.createCall({
            ...data,
            sip_call_id: inviterSession.request.getHeader("Call-ID"),
        });
        onCallRecordCreationStarted?.();
        const session = this._createSession({
            callProm,
            createDate,
            direction: "outgoing",
            phone_number: data.phone_number,
            alias: data.alias,
            outboundNumber,
            sipSession: inviterSession,
            transferTarget: willCallFromAnotherDevice ? this.makeUri(target.number) : null,
        });
        if (transferFromSessionKey) {
            this.transferPairs.push([transferFromSessionKey, session.key]);
        }
        try {
            await session.invite(willCallFromAnotherDevice);
        } catch (error) {
            this._removeSession(session);
            if (!session.cancelRequested) {
                console.error(error);
                this.voip.triggerError({
                    isBlocking: false,
                    message: _t(
                        "An error occurred trying to invite the following number: %(phoneNumber)s",
                        { phoneNumber: data.phone_number }
                    ),
                    technical: error.name,
                    technicalExtra: error.message,
                });
            }
            return false;
        }
        this.voip.softphone.inCallView.activeView = "default";
        this.voip.softphone.show();
        return true;
    }

    /**
     * @param {string} phoneNumber
     * @returns {import("sip.js").URI}
     */
    makeUri(phoneNumber) {
        const sanitizedNumber = cleanPhoneNumber(phoneNumber);
        return SIP.UserAgent.makeURI(`sip:${sanitizedNumber}@${this.voip.config.pbxAddress}`);
    }

    performAttendedTransfer(frontSessionKey) {
        const pair = this.transferPairs.find((p) => p.includes(frontSessionKey));
        if (!pair) {
            return;
        }
        const [mainKey, transferKey] = pair;
        const mainSession = this.sessions[mainKey];
        const transferSession = this.sessions[transferKey];
        if (!mainSession?.isOngoing || !transferSession?.isOngoing) {
            return;
        }
        mainSession.refer(transferSession, {
            onNotify: ({ incomingNotifyRequest }) => {
                if (incomingNotifyRequest.message.body.includes("200 OK")) {
                    mainSession.hangup();
                }
            },
        });
    }

    /**
     * Makes sure to updates sessions with a microphone stream or show an error
     * if not possible. Note that if the permission is switched on, the
     * AudioManager instance already does this automatically but without forcing
     * a potential error to be shown (which we want because it is a valid use-
     * case to use the softphone without microphone, as there will still be the
     * microphone status being shown either way).
     */
    establishMicrophoneUsage() {
        this.audioManager.applyInputDeviceToSessions(true);
    }

    updateIncomingRingtone() {
        const session = this.callInvitationSession;
        if (!session) {
            return;
        }
        if (this.isInDoNotDisturbMode) {
            session.ringtone.stop();
        } else {
            this.requestIncomingRingtone();
        }
    }

    requestIncomingRingtone() {
        if (this.hasCallInvitation && !this.isInDoNotDisturbMode) {
            const session = this.callInvitationSession;
            if (session?.ringleader) {
                session.ringtone.play("incoming");
            }
        }
    }

    /**
     * Broadcasts a message to all devices of the same user via the bus.
     *
     * @param {string} messageType
     * @param {Object} [payload={}]
     */
    _broadcast(messageType, payload = {}) {
        return this.orm.call("res.users", "action_voip_bus_send", [
            messageType,
            { senderUUID: this.UUID, senderSeq: ++this._broadcastSeq, ...payload },
        ]);
    }

    /**
     * @param {string} messageType
     * @param {Object} [payload={}]
     */
    _broadcastAsPuller(messageType, payload = {}) {
        return this._broadcast(messageType, {
            pullId: this.pull.id,
            targetUUID: this.pull.targetUUID,
            ...payload,
        });
    }

    /**
     * @param {string} messageType
     * @param {Object} [payload={}]
     */
    _broadcastAsPusher(messageType, payload = {}) {
        return this._broadcast(messageType, {
            pullId: this.push.pullId,
            targetUUID: this.push.targetUUID,
            ...payload,
        });
    }

    /**
     * @param {string} type
     * @param {Function} handler
     */
    _subscribeBroadcast(type, handler) {
        this.busService.subscribe(type, (payload) => {
            if (
                payload.senderUUID === this.UUID ||
                (payload.targetUUID && payload.targetUUID !== this.UUID) ||
                payload.exceptUUID === this.UUID
            ) {
                return;
            }
            handler.call(this, payload);
        });
    }

    /**
     * @param {string} type
     * @param {Function} handler
     */
    _subscribeAsPuller(type, handler) {
        this._subscribeBroadcast(type, (payload) => {
            if (!this._isStillPulling(payload.pullId)) {
                return;
            }
            handler.call(this, payload);
        });
    }

    /**
     * @param {string} type
     * @param {Function} handler
     */
    _subscribeAsPusher(type, handler) {
        this._subscribeBroadcast(type, (payload) => {
            if (!this._isStillPushing(payload.pullId)) {
                return;
            }
            handler.call(this, payload);
        });
    }

    /**
     * Marks phone numbers as ignored for 10 seconds so that re-INVITEs
     * triggered by a REFER (on the pushing device) or suppressed calls (on
     * bystander devices) are silently discarded instead of ringing.
     *
     * @param {string[]} phoneNumbers
     */
    _ignorePhoneNumbers(phoneNumbers) {
        for (const phoneNumber of phoneNumbers) {
            this._ignoredPhoneNumbers.add(phoneNumber);
        }
        // Safety cleanup: remove from the ignore list after 10 seconds in
        // case the expected INVITE never arrives (e.g. network issue). Under
        // normal conditions, the number is removed earlier when the INVITE
        // is received in _onIncomingInvitation.
        setTimeout(() => {
            for (const phoneNumber of phoneNumbers) {
                this._ignoredPhoneNumbers.delete(phoneNumber);
            }
        }, 10_000);
    }

    /**
     * Initiates a pull: asks the remote agent with active calls to transfer
     * them to this tab. Sets up a 20-second safety timer to abandon the pull
     * if no response is received.
     *
     * @returns {Promise<void>}
     */
    async pullAllCalls() {
        if (this.hasTransferInProgress) {
            return;
        }
        if (this.voip.config.mode !== "prod") {
            this.notification.add(_t("Transferring calls is not supported in demo mode."), {
                type: "warning",
            });
            return;
        }
        const targetUUID = this.lastNonLocalActiveUserAgentUUID;
        if (!targetUUID) {
            return;
        }
        const pullId = crypto.randomUUID();
        this.pull = {
            id: pullId,
            targetUUID,
            pendingEntries: [],
        };
        // 20s unconditional safety cleanup. Any entry whose replacement
        // INVITE never arrived is explicitly failed and its call ended here,
        // instead of leaving it "ongoing" until the stuck-calls cron (which
        // can take hours) eventually cleans it up.
        setTimeout(() => {
            if (!this._isStillPulling(pullId)) {
                return;
            }
            this.notification.add(_t("Switching calls to this tab was abandoned"), {
                type: "warning",
            });
            for (const entry of this.pull.pendingEntries) {
                if (entry.settled) {
                    // Already resolved (succeeded, or explicitly failed by
                    // the pusher) — its call must not be touched here.
                    continue;
                }
                entry.deferred.resolve(null);
                this.voip.getCallById(entry.voip_call_id).then((call) => call?.end());
            }
            if (!this.pull.pendingEntries.length) {
                // _onPendingEntries never started (the pusher never replied
                // in time), so nothing else will clear `pull`. Otherwise,
                // resolving the entries above lets its own awaited
                // Promise.all settle and clear `pull` itself, after reporting
                // the final result — clearing it here too would make that
                // report see an already-abandoned pull and skip it.
                this.pull = null;
            }
        }, 20_000);
        this.notification.add(_t("Switching calls to this tab..."), { type: "info" });
        this._broadcastAsPuller("voip.call.pull/initiate");
    }

    /**
     * Handles a pull request from a remote tab. Broadcasts suppress_invite to
     * all bystander agents, then sends the list of ongoing calls
     * (pendingEntries) to the puller and waits for an acknowledgement before
     * issuing SIP REFERs one by one. Each REFER asks the PBX to re-invite the
     * puller; on acceptance the local session is hung up.
     *
     * @param {{pullId: string, senderUUID: string}} param0
     */
    async _onPullInitiate({ pullId, senderUUID }) {
        if (this.hasTransferInProgress) {
            return;
        }
        const sessions = this._ongoingSessions;
        if (!sessions.length) {
            return;
        }
        this.push = { pullId, targetUUID: senderUUID };
        setTimeout(() => {
            if (this._isStillPushing(pullId)) {
                this.push = null;
            }
        }, 20_000);

        // Wait for all call records to be resolved before building
        // pendingEntries, so that voip_call_id is always known.
        await Promise.all(sessions.map((s) => s.callProm));
        if (!this._isStillPushing(pullId)) {
            // The 20s safety timer fired (or another pull took over) while we
            // were awaiting the call records; abort before touching `this.push`.
            return;
        }

        const pendingEntries = [];
        const phoneNumbers = [];
        for (const s of sessions) {
            pendingEntries.push({
                sessionKey: s.key,
                phone_number: s.phone_number,
                voip_call_id: s.call.id,
                is_front: s.key === this.frontSession?.key,
            });
            phoneNumbers.push(s.phone_number);
        }

        this._broadcast("voip.call.pull/suppress_invite", {
            phone_numbers: phoneNumbers,
            exceptUUID: senderUUID,
        });
        await new Promise((resolve) => {
            this.push.resolve = resolve;
            this._broadcastAsPusher("voip.call.pull/pending_entries", { pendingEntries });
        });
        if (!this._isStillPushing(pullId)) {
            return;
        }
        for (const { phone_number, sessionKey } of pendingEntries) {
            const session = this.sessions[sessionKey];
            if (!session?.isOngoing) {
                this._broadcastAsPusher("voip.call.pull/entry_failed", { sessionKey });
                continue;
            }
            this._ignorePhoneNumbers([phone_number]);
            try {
                await new Promise((resolve, reject) => {
                    session
                        .refer(this.uri, {
                            requestDelegate: {
                                onAccept: () => {
                                    // Skip the end_call RPC: the call is still ongoing
                                    // on the puller's device.
                                    //
                                    // If the replacement INVITE never reaches the puller,
                                    // its 20s timeout ends the call. A PBX acknowledgement
                                    // could detect this earlier but is not required for
                                    // cleanup.
                                    session.skipServerUpdate = true;
                                    session.hangup();
                                    resolve();
                                },
                                onReject: reject,
                            },
                        })
                        .catch(reject);
                });
            } catch (error) {
                console.warn("Cross-tab call transfer rejected.", error);
                if (this._isStillPushing(pullId)) {
                    this._broadcastAsPusher("voip.call.pull/entry_failed", { sessionKey });
                }
            }
        }
    }

    /**
     * Received by bystander agents: marks the given phone numbers as ignored
     * so that the re-INVITEs from the PBX are silently discarded.
     *
     * @param {{phone_numbers: string[]}} param0
     */
    _onSuppressInvite({ phone_numbers }) {
        this._ignorePhoneNumbers(phone_numbers);
    }

    /**
     * Received by the puller: stores the pending entries from the pusher,
     * acknowledges receipt, then waits for each session to be accepted before
     * notifying the pusher of the final result.
     *
     * @param {{pendingEntries: Array<{sessionKey: string, phone_number: string, voip_call_id: number, is_front: boolean}>, pullId: string}} param0
     */
    async _onPendingEntries({ pendingEntries, pullId }) {
        const entries = pendingEntries.map((raw) => {
            const entry = { ...raw, settled: false };
            const { promise, resolve } = Promise.withResolvers();
            entry.deferred = {
                promise,
                // Track settlement so the 20s safety timeout in pullAllCalls
                // does not end a call whose entry already succeeded or was
                // explicitly failed by the pusher.
                resolve: (value) => {
                    entry.settled = true;
                    resolve(value);
                },
            };
            return entry;
        });
        this.pull.pendingEntries = entries;
        this._broadcastAsPuller("voip.call.pull/pending_entries_received");
        const results = await Promise.all(entries.map((e) => e.deferred.promise));
        if (!this._isStillPulling(pullId)) {
            return;
        }
        const succeeded = results.filter(Boolean).length;
        const failed = results.length - succeeded;
        this._broadcastAsPuller("voip.call.pull/result", { succeeded, failed });
        this._notifyTransferResult(succeeded, failed, "pull");
        this.pull = null;
    }

    /** @param {{sessionKey: string}} param0 */
    _onPullEntryFailed({ sessionKey }) {
        const entry = this.pull.pendingEntries.find((entry) => entry.sessionKey === sessionKey);
        entry?.deferred.resolve(null);
    }

    /**
     * Received by the pusher: the puller acknowledged the pending entries,
     * unblocking the REFER loop in `_onPullInitiate`.
     */
    _onPendingEntriesReceived() {
        this.push.resolve();
    }

    /**
     * Received by the pusher: displays the transfer result notification and
     * clears the push state.
     *
     * @param {{succeeded: number, failed: number}} param0
     */
    _onPullResult({ succeeded, failed }) {
        this._notifyTransferResult(succeeded, failed, "push");
        this.push = null;
    }

    /**
     * Builds the data payload for `getOrCreateCall` from an incoming INVITE.
     *
     * @param {import("sip.js").Invitation} inviteSession
     * @returns {Object}
     */
    _buildIncomingCallData(inviteSession) {
        const sipCallId = inviteSession.request.getHeader("Call-ID");
        // Only the Odoo provider's PBX is trusted to stamp this header; another
        // provider could be relaying a value forged by the remote caller.
        const conversationId = this.voip.config.usesOdooProvider
            ? inviteSession.request.getHeader("X-Odoo-Conversation-Id")
            : null;
        return {
            // Sent apart from the Call-ID rather than collapsed with it: the
            // server correlates on the conversation when there is one, and on
            // the Call-ID otherwise, and cannot tell the two apart once merged.
            conversation_identifier: conversationId,
            direction: "incoming",
            phone_number: inviteSession.remoteIdentity.uri.user,
            // The PBX webhook stores this same value as `sip_call_id`. Sending
            // it to the server lets get_or_create attach this INVITE to the
            // call record created earlier by the webhook.
            sip_call_id: sipCallId,
        };
    }

    /**
     * @param {Object} callData
     * @returns {Object|undefined}
     */
    _consumePendingEntry(callData) {
        // TODO: matching by phone number is ambiguous when multiple pending
        // transfers share the "same" number. A safer fix is to *fully* complete
        // one pending entry at a time, (or carry a better transfer correlation
        // key through the re-INVITE path but this did not seem possible). At
        // the moment, we make one REFER at a time but it still does not
        // guarantee re-INVITE correct order.
        const index =
            this.pull?.pendingEntries.findIndex((p) =>
                isSamePhoneNumber(callData.phone_number, p.phone_number)
            ) ?? -1;
        return index >= 0 ? this.pull.pendingEntries.splice(index, 1)[0] : undefined;
    }

    /**
     * Handles an incoming INVITE that is part of a device transfer (pull).
     * The call record already exists on the server; we fetch it by ID,
     * create a local session, and auto-accept.
     *
     * @param {import("sip.js").Invitation} inviteSession
     * @param {Object} callData
     * @param {Object} pendingEntry
     */
    _onTransferInvitation(inviteSession, callData, pendingEntry) {
        const callProm = this.voip.getCallById(pendingEntry.voip_call_id);
        const session = this._createSession(
            {
                callProm,
                createDate: luxon.DateTime.now(),
                direction: callData.direction,
                phone_number: callData.phone_number,
                sipSession: inviteSession,
            },
            { promote: false }
        );
        session
            .accept({ promote: pendingEntry.is_front, suppressError: false })
            .then(() => {
                pendingEntry.deferred.resolve(pendingEntry.sessionKey);
            })
            .catch(() => {
                // Transfer failed on the puller side. The pusher already
                // skipped end_call (skipServerUpdate), so we must terminate the
                // call record here, otherwise it stays "ongoing" with no active
                // SIP session on either side.
                callProm.then((call) => call?.end());
                pendingEntry.deferred.resolve(null);
            });
        this.voip.softphone.show();
        return session;
    }

    /** @param {import("sip.js").Invitation} inviteSession */
    _onIncomingInvitation(inviteSession) {
        const createDate = luxon.DateTime.now();
        this.voip.resolveError();
        const callData = this._buildIncomingCallData(inviteSession);

        const pendingEntry = this._consumePendingEntry(callData);
        if (pendingEntry) {
            return this._onTransferInvitation(inviteSession, callData, pendingEntry);
        }
        if (this._ignoredPhoneNumbers.delete(callData.phone_number)) {
            return;
        }

        const callProm = this.voip.getOrCreateCall(callData);
        // Add the incoming session without promoting it to the front —
        // the hold/promote happens only when the user explicitly accepts the call.
        const session = this._createSession(
            {
                callProm,
                createDate,
                direction: callData.direction,
                phone_number: callData.phone_number,
                sipSession: inviteSession,
            },
            { promote: false }
        );
        session.skipServerUpdate = this.voip.config.usesOdooProvider;
        // Notification clicks can arrive before the browser receives the
        // INVITE. Match by control handle, the primary correlation key between
        // PBX webhooks and browser INVITEs, so the pending action fires even
        // before this browser's own SIP leg is recorded.
        const controlHandle = callData.conversation_identifier || callData.sip_call_id;
        const shouldAutoAnswer = this._shouldAnswerToControlHandles.has(controlHandle);
        const shouldAutoDecline = this._shouldDeclineToControlHandles.has(controlHandle);
        this._shouldAnswerToControlHandles.delete(controlHandle);
        this._shouldDeclineToControlHandles.delete(controlHandle);
        if (shouldAutoDecline) {
            session.hangup();
            return session;
        }
        if (shouldAutoAnswer) {
            session.skipServerUpdate = true;
            this.voip.softphone.show();
            session.accept();
        }
        if (navigator.userActivation.hasBeenActive) {
            // we use a service we do not depend on!
            this.env.services["voip.worker"].send("VOIP:RING?", {
                controlHandle,
                sessionKey: session.key,
            });
        }
        if (!this.isInDoNotDisturbMode) {
            this.voip.softphone.show();
        }

        return session;
    }

    /**
     * Triggered when the transport transitions from connected state.
     *
     * @param {Error} error
     */
    _onTransportDisconnected(error) {
        if (!error) {
            return;
        }
        console.error(error);
        this.attemptReconnection();
    }

    /**
     * @param {Session} session
     * @param {import("sip.js").Web.SessionDescriptionHandler} sessionDescriptionHandler
     * @param {"incoming"|"outgoing"} direction
     * @param {Function} onRemoteTrackAdded
     * @param {Function} [onLocalTrackUpdated]
     */
    _onSessionDescriptionHandler(
        session,
        sessionDescriptionHandler,
        direction,
        onRemoteTrackAdded,
        onLocalTrackUpdated
    ) {
        this.audioManager.setupSessionDescriptionHandler(
            sessionDescriptionHandler,
            direction,
            onRemoteTrackAdded,
            onLocalTrackUpdated
        );
    }

    /**
     * @param {Session} session
     */
    _onSessionStateEstablished(session) {
        if (this._ongoingSessionCount === 1) {
            this._broadcast("voip/agent_state", { active: true });
        }
    }

    _onSessionStateTerminated(session) {
        this._removeSession(session);
        if (this._ongoingSessionCount === 0) {
            this._broadcast("voip/agent_state", { active: false });
        }
        if (this._sessionCount === 0) {
            if (!this.push) {
                this.voip.softphone.showCallSummary(session);
            }
            this.voip.softphone.dialer.reset();
            this.voip.softphone.inCallView.reset();
        }
    }
}
