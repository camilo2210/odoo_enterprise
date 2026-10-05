import { Component, onWillStart, signal, useEffect, useListener } from "@odoo/owl";
import { Agenda } from "@voip/softphone/agenda";
import { CallInvitation } from "@voip/softphone/call_invitation";
import { CallSummary } from "@voip/softphone/call_summary";
import { Dialer } from "@voip/softphone/dialer";
import { StatusMenu } from "@voip/softphone/status_menu";
import { ErrorScreen } from "@voip/softphone/error_screen";
import { History } from "@voip/softphone/history";
import { InCallView } from "@voip/softphone/in_call_view";
import { isCurrentFocusEditable } from "@voip/utils/utils";
import { isMobileOS } from "@web/core/browser/feature_detection";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";
import { useActiveElement } from "@web/core/ui/ui_plugin";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { render } from "@web/owl2/utils";

export class Softphone extends Component {
    static components = {
        Agenda,
        CallInvitation,
        Dialer,
        StatusMenu,
        ErrorScreen,
        CallSummary,
        History,
        InCallView,
    };
    static template = "voip.Softphone";

    softphoneRef = signal.ref();

    setup() {
        this.voip = useService("voip");
        useListener(this.voip.bus, "session_changed", () => render(this, true));
        this.userAgent = this.voip.userAgent;
        this.softphone = this.voip.softphone;
        onWillStart(async () => {
            this.isUserVoipAdmin = await user.hasGroup("voip.group_voip_admin");
        });
        useActiveElement(this.softphoneRef);
        useHotkey("Escape", () => this.softphone.hide());
        const softphone = this.voip.softphone;
        useEffect(() => {
            const input = softphone.searchInput();
            const shouldFocus = softphone.shouldFocus();
            if (input && !this.voip.error && !isCurrentFocusEditable()) {
                input.focus();
            }
            if (shouldFocus) {
                softphone.shouldFocus.set(false);
            }
        });
    }

    /** @returns {string} */
    get activeTab() {
        return this.softphone.activeTab;
    }

    /** @returns {?import("@voip/core/web/session").Session[]} */
    get backSessions() {
        const excludedKeys = [this.frontSession?.key, this.userAgent.callInvitationSession?.key];
        return Object.values(this.userAgent.sessions)
            .filter((s) => !excludedKeys.includes(s.key))
            .reverse();
    }

    /** @returns {?import("@voip/core/web/session").Session} */
    get frontSession() {
        return this.userAgent.frontSession;
    }

    /** @returns {boolean} */
    get isOnSmallDevice() {
        return this.env.services.ui.isSmall;
    }

    /** @returns {boolean} */
    get isTransferConfirmation() {
        return Boolean(
            this.frontSession &&
                this.softphone.inCallView.activeView === "transfer" &&
                this.softphone.inCallView.transferView.activeView === "confirmation"
        );
    }

    /** @returns {boolean} */
    get showDeviceSelection() {
        return this.voip.hasRtcSupport && !isMobileOS();
    }

    /** @returns {boolean} */
    get showAudioActivation() {
        return this.voip.hasRtcSupport && isMobileOS();
    }

    /** @returns {{ icon: string, iconClasses: string, isRinging: boolean, text: string, title: string }|undefined} */
    get callStatus() {
        if (!this.frontSession && !this.userAgent.hasCallInvitation) {
            return undefined;
        }
        return {
            icon: this.topBarIcon,
            iconClasses: this.topBarIconClasses,
            isRinging: this.userAgent.hasCallInvitation,
            text: this.topBarText,
            title: this.topBarTitle,
        };
    }

    get tabs() {
        return [
            { id: "recent", name: _t("Recent"), icon: "history" },
            { id: "dialer", name: _t("Keypad"), icon: "dialpad" },
            { id: "activities", name: _t("Activities"), icon: "schedule" },
        ];
    }

    /** @returns {string} */
    get topBarIcon() {
        if (this.frontSession?.isOnHold) {
            return "pause";
        }
        if (this.voip.microphoneError) {
            return "error";
        }
        return "phone";
    }

    /** @returns {string} */
    get topBarIconClasses() {
        if (this.frontSession?.isOnHold) {
            return "text-warning";
        }
        return this.voip.microphoneError ? "oi-filled text-danger" : "oi-filled text-success";
    }

    /** @returns {string} */
    get topBarTitle() {
        return this.voip.microphoneError && !this.frontSession?.isOnHold
            ? this.voip.microphoneError
            : this.topBarText;
    }

    /** @returns {string} */
    get topBarText() {
        if (this.userAgent.hasCallInvitation) {
            return _t("Incoming call…");
        }
        if (!this.frontSession) {
            return "";
        }
        if (this.frontSession.ringsBack) {
            return _t("Ringing…");
        }
        if (this.frontSession.isCalling) {
            return _t("Outgoing call…");
        }
        if (this.frontSession.isOngoing) {
            return _t("%(status)s - %(timer)s", {
                status: this.frontSession.statusText,
                timer: this.frontSession.timerText,
            });
        }
        return _t("In call");
    }

    onClickClose() {
        this.softphone.hide();
    }

    onClickCancelTransfer() {
        this.softphone.inCallView.transferView.activeView = "contacts";
    }

    onClickSwitchHere() {
        this.userAgent.pullAllCalls();
    }

    /** @param {string} tabId */
    onClickTab(tabId) {
        this.softphone.hideCallSummary();
        this.softphone.activeTab = tabId;
        this.voip.softphone.shouldFocus.set(true);
    }
}
