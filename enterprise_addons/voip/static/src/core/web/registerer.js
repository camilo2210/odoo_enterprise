import { _t } from "@web/core/l10n/translation";

export class Registerer {
    /**
     * When sending a REGISTER request, an “expires” parameter with the value of
     * this field is added to the Contact header. It is used to indicate how
     * long we would like the registration to remain valid.
     * Note however that the definitive value is decided by the server based on
     * its own policy and may therefore differ.
     *
     * The library automatically renews the registration for the same duration
     * shortly before it expires.
     *
     * The value is expressed in seconds.
     */
    static EXPIRATION_INTERVAL = 600;
    static REGISTRATION_RETRY_INTERVAL = 2_000;
    static REGISTRATION_RETRY_ATTEMPTS = 8;
    /** @type {import("@voip/core/web/voip_service").Voip} */
    voip;
    /**
     * @type {import("sip.js").Registerer}
     * An instance of the Registerer class from the SIP.js library. It shouldn't
     * be used outside of this class; only this class is responsible for
     * interfacing with this object.
     */
    __sipJsRegisterer;

    isRegistered = false;
    _onBeforeUnload;
    _registrationRetryCount = 0;
    _registrationRetryTimeout;

    /**
     * @param {import("@voip/core/web/voip_service").Voip} voip
     * @param {import("sip.js").UserAgent} sipJsUserAgent
     */
    constructor(voip, sipJsUserAgent) {
        this.voip = voip;
        this.__sipJsUserAgent = sipJsUserAgent;
        this._createSipJsRegisterer();
        this._onBeforeUnload = () => {
            voip.isUnloading = true;
            this.__sipJsRegisterer.unregister();
            setTimeout(() => {
                // if this runs, the unload has most likely been canceled;
                // reestablish the connection
                voip.isUnloading = false;
                this.voip.userAgent.attemptReconnection();
            }, 7_500);
        };
        window.addEventListener("beforeunload", this._onBeforeUnload);
    }

    _createSipJsRegisterer() {
        this.__sipJsRegisterer = new SIP.Registerer(this.__sipJsUserAgent, {
            expires: Registerer.EXPIRATION_INTERVAL,
            // Activates reg-id and +sip.instance support in REGISTER requests
            // for Odoo Phone Provider. These two Contact attributes are required
            // by our edge infra in order to support RFC5626 flow-tokens.
            // See: https://www.rfc-editor.org/info/rfc5626/#section-5
            regId: this.voip.config.usesOdooProvider ? 1 : undefined,
        });
        this._onStateChangedListener = (state) => this._onStateChanged(state);
        this.__sipJsRegisterer.stateChange.addListener(this._onStateChangedListener);
    }

    _reset() {
        this.__sipJsRegisterer.stateChange.removeListener(this._onStateChangedListener);
        this.__sipJsRegisterer.dispose();
        this._createSipJsRegisterer();
    }

    /**
     * Sends the REGISTER request to the Registrar.
     */
    register() {
        this._clearRegistrationRetry();
        return this._sendRegister();
    }

    _sendRegister() {
        if (this.__sipJsRegisterer.waiting) {
            // When the WebSocket drops while a REGISTER is in flight, SIP.js
            // can keep this flag set until Timer F expires (~32s). Reconnecting
            // on the same instance would then reject with RequestPendingError,
            // so this recreates it before sending a fresh REGISTER.
            // Do not reset a healthy registerer: disposing a registered
            // instance sends an unregister that can race with the new register.
            this._reset();
        }
        return this.__sipJsRegisterer.register({
            requestDelegate: {
                onReject: (response) => this._onRegistrationRejected(response),
            },
        });
    }

    unregister() {
        this._clearRegistrationRetry();
        return this.__sipJsRegisterer.unregister();
    }

    destroy() {
        window.removeEventListener("beforeunload", this._onBeforeUnload);
        return this.unregister();
    }

    /**
     * Triggered when receiving a response with status code 4xx, 5xx, or 6xx to
     * the REGISTER request.
     *
     * @param {import("sip.js").Core.IncomingResponse} response The server final response to the
     * REGISTER request.
     */
    _onRegistrationRejected(response) {
        let message = "";
        let technicalExtra = "";
        switch (response.message.statusCode) {
            // Unauthorized
            case 401: {
                if (this._registrationRetryCount < Registerer.REGISTRATION_RETRY_ATTEMPTS) {
                    this._registrationRetryCount++;
                    this._registrationRetryTimeout = setTimeout(
                        () => this._sendRegister(),
                        Registerer.REGISTRATION_RETRY_INTERVAL
                    );
                    return;
                }
                message = _t(
                    // See areCredentialsSet (if not set, it basically triggers
                    // the same error message).
                    "The connection failed. Your login or provider details in your user preferences for the phone might be incorrect. Please check or ask your administrator to check if needed."
                );
                technicalExtra = _t(
                    "Server authentication failure. Verify that the server (i.e. PBX server IP) in the VoIP Provider Settings and the credentials in your user preferences are correct."
                );
                break;
            }
            // Service Unavailable
            case 503: {
                // Note that transport layer failures would trigger 503 but
                // would generally trigger other errors before this one happens.
                // So here we prefer to only tell the user to try again.
                message = _t(
                    "Service unavailable. Refresh the page and try again. If the problem persists, please try again later or ask your administrator for additional help."
                );
                break;
            }
            default: {
                message = _t(
                    "The connection failed. Please try again later. If the problem persists, please ask your administrator to check the configuration."
                );
            }
        }
        this.voip.triggerError({
            message: message,
            technical: _t("Registration rejected: %(code)s %(reason)s.", {
                code: response.message.statusCode,
                reason: response.message.reasonPhrase,
            }),
            technicalExtra: technicalExtra,
        });
    }

    _clearRegistrationRetry() {
        clearTimeout(this._registrationRetryTimeout);
        this._registrationRetryCount = 0;
        this._registrationRetryTimeout = undefined;
    }

    _onStateChanged(newState) {
        this.isRegistered = newState === SIP.RegistererState.Registered;
        if (this.isRegistered) {
            this._clearRegistrationRetry();
            this.voip.resolveError();
        }
        this.voip.bus.trigger("registerer_changed");
    }
}
