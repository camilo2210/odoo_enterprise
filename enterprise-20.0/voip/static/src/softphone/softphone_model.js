import { _t } from "@web/core/l10n/translation";

import { InCallViewModel } from "@voip/softphone/in_call_view_model";
import { KeypadModel } from "@voip/softphone/keypad_model";
import { isSubstring, matchPhoneNumber } from "@voip/utils/utils";
import { computed, proxy, signal } from "@odoo/owl";

export const VOIP_PAGE_SIZE = 13;

/**
 * Retains the state of the Softphone that needs to be persisted even if the
 * corresponding component is unmounted.
 */
export class Softphone {
    activeTab = "recent";
    activeTabSection = "";
    activeRecord = null;
    dialer = new KeypadModel();
    isDisplayed = false;
    addressBook = {
        searchInputValue: "",
    };
    agenda = {
        searchInputValue: "",
    };
    callSummary = {
        /**
         * @type {import("@voip/core/web/session").Session}
         */
        session: null,
        isShown: false,
        hideAfterTimeout: undefined,
        scrollToActiveRecord: false,
    };
    history = {
        previousTab: null,
        selectedContact: null,
        searchInputValue: "",
    };
    historyRefreshKey = 0;
    inCallView = new InCallViewModel();
    searchInput = signal.ref();
    shouldFocus = signal(false);
    shouldBeOnTop = computed(
        () => this.userAgent.hasCallInvitation && !this.userAgent.isInDoNotDisturbMode
    );

    constructor(store, userAgent) {
        this.store = store;
        this.userAgent = userAgent;
        this.setup();
        return proxy(this);
    }

    get activities() {
        const searchInputValue = this.agenda.searchInputValue.trim();
        return [...this.store["mail.activity"].records.values()].filter(
            (activity) =>
                activity.activity_category === "phonecall" &&
                ["today", "overdue"].includes(activity.state) &&
                activity.phone &&
                activity.user_id.eq(this.store.self_user) &&
                (!searchInputValue ||
                    [
                        activity.partner.complete_name,
                        activity.partner.displayName,
                        activity.name,
                    ].some((x) => isSubstring(x, searchInputValue)) ||
                    matchPhoneNumber(activity.phone, searchInputValue))
        );
    }

    get contacts() {
        return [...this.store["res.partner"].records.values()].filter((partner) =>
            Boolean(partner.phone)
        );
    }

    /** @returns {Object} */
    get audioPermissionDialogConfiguration() {
        return {
            props: {
                suggestAllMedias: false,
                permissionPrompt: _t("Do you want people to hear you in the call?"),
            },
            options: {
                // Imperfect: we let discuss's permission management handle
                // calls to navigator.mediaDevices.getUserMedia but re-do it
                // ourselves here afterwards (both if it succeeds or fails to
                // updates calls or show technical errors). We might want to
                // re-wires things to better share the code between discuss' RTC
                // service and VoIP's audio manager, but it might also be better
                // to keep created MediaStream separated in any case.
                onClose: (closeParams) => {
                    if (!closeParams?.dismiss) {
                        this.userAgent.establishMicrophoneUsage();
                    }
                },
            },
        };
    }

    /**
     * Setup method to be overridden by subclasses.
     * This method exists because the constructor cannot be overridden,
     * allowing subclasses to perform initialization logic.
     */
    setup() {}

    hide() {
        this.userAgent?.voip?.invalidatePrefill();
        this.clearActiveRecord();
        this.isDisplayed = false;
        if (this.userAgent?.hasCallInvitation) {
            this.userAgent.callInvitationSession.ringtone.stop();
        }
    }

    hideCallSummary() {
        clearTimeout(this.callSummary.hideAfterTimeout);
        Object.assign(this.callSummary, {
            session: null,
            hideAfterTimeout: undefined,
            isShown: false,
        });
    }

    clearActiveRecord() {
        this.activeRecord = null;
        this.activeTabSection = "";
    }

    openContactHistory(contact, { previousTab = null } = {}) {
        this.clearActiveRecord();
        this.history.previousTab = previousTab;
        this.history.selectedContact = contact;
        this.history.searchInputValue = "";
        this.activeTab = "recent";
    }

    showRecent() {
        this.hideCallSummary();
        this.callSummary.scrollToActiveRecord = false;
        this.openContactHistory(null);
        this.historyRefreshKey++;
        this.show();
    }

    show() {
        this.userAgent.env.services["voip.pip"]?.close();
        this.isDisplayed = true;
        this.userAgent.requestIncomingRingtone();
    }

    showCallSummary(session) {
        clearTimeout(this.callSummary.hideAfterTimeout);
        Object.assign(this.callSummary, {
            session,
            hideAfterTimeout: setTimeout(() => {
                this.hideCallSummary();
                this.callSummary.scrollToActiveRecord = true;
            }, 3000),
            isShown: true,
        });
    }
}
