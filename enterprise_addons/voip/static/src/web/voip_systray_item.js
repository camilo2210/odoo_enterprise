import { Component, useListener } from "@odoo/owl";
import { SessionRecorder } from "@voip/core/web/session_recorder";
import { useCommand } from "@web/core/commands/command_hook";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { render } from "@web/owl2/utils";

export class VoipSystrayItem extends Component {
    static template = "voip.SystrayItem";

    setup() {
        this.voip = useService("voip");
        this.ui = useService("ui");
        useListener(this.voip.bus, "session_changed", () => render(this, true));
        this.userAgent = this.voip.userAgent;
        this.softphone = this.voip.softphone;
        this.uploadsByRecorder = SessionRecorder.uploadsByRecorder;
        useCommand(_t("Toggle Softphone"), () => this.toggleSoftphone(), { hotkey: "Alt+Shift+S" });
    }

    /**
     * Checks if any SessionRecorder instance currently has active upload promises.
     * Used to display the "Processing..." state in the systray.
     *
     * @returns {boolean}
     */
    get isUploadInProgress() {
        return SessionRecorder.isUploadInProgress();
    }

    get frontSession() {
        return this.userAgent.frontSession;
    }

    /** @returns {boolean} */
    get hasOngoingCall() {
        return this.frontSession?.isOngoing;
    }

    /** @returns {string} */
    get icon() {
        if (this.frontSession?.isOnHold) {
            return "pause";
        }
        return "phone";
    }

    /**
     * Number of missed calls used to display in systray item icon.
     *
     * @returns {number}
     */
    get missedCallCount() {
        return this.voip.missedCalls;
    }

    /**
     * Translated text used as the title attribute of the systray item.
     *
     * @returns {string}
     */
    get titleText() {
        return this.softphone.isDisplayed ? _t("Hide Softphone") : _t("Show Softphone");
    }

    /** @returns {string} */
    get systrayButtonClasses() {
        if (this.ui.isSmall && !this.voip.canCall) {
            return "d-none";
        }
        if (this.userAgent.hasCallInvitation) {
            return "text-success";
        }
        if (this.isUploadInProgress) {
            return "rounded-pill px-2 bg-warning text-warning-emphasis";
        }
        if (this.frontSession?.isOnHold) {
            return "rounded-pill px-2 bg-warning-subtle text-warning-emphasis";
        }
        if (this.hasOngoingCall) {
            return "rounded-pill px-2 bg-success-subtle text-success-emphasis";
        }
        return "";
    }

    /** @returns {ReturnType<_t>|""} */
    get systrayButtonText() {
        if (this.isUploadInProgress) {
            return _t("Processing…");
        }
        return this.frontSession?.statusText ?? "";
    }

    /** @param {MouseEvent} ev */
    onClick(ev) {
        this.toggleSoftphone();
    }

    async toggleSoftphone() {
        if (this.softphone.isDisplayed) {
            this.softphone.hide();
        } else {
            document.activeElement.blur();
            if (this.voip.missedCalls > 0) {
                this.voip.resetMissedCalls();
            }
            if (!this.voip.canCall) {
                await this.voip.refreshConfig();
            }
            this.voip.prefillFromActiveForm();
            this.softphone.show();
        }
    }
}
