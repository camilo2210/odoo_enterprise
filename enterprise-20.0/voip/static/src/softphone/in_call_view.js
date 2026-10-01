import { Component, proxy, t, useListener, useProps } from "@odoo/owl";
import { Session } from "@voip/core/web/session";
import { ActionButton } from "@voip/softphone/action_button";
import { ActionList } from "@voip/softphone/action_list";
import { AddCallView } from "@voip/softphone/add_call_view";
import { CallBanner } from "@voip/softphone/call_banner";
import { ContactInfo } from "@voip/softphone/contact_info";
import { Keypad } from "@voip/softphone/keypad";
import { TransferConfirmation } from "@voip/softphone/transfer_confirmation";
import { TransferView } from "@voip/softphone/transfer_view";
import { isCurrentFocusEditable } from "@voip/utils/utils";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class InCallView extends Component {
    static components = {
        ActionButton,
        AddCallView,
        ActionList,
        CallBanner,
        ContactInfo,
        Keypad,
        TransferConfirmation,
        TransferView,
    };
    static template = "voip.InCallView";

    props = useProps({
        backSessions: t.array(),
        frontSession: t.instanceOf(Session),
    });

    setup() {
        this.voip = useService("voip");
        this.softphone = this.voip.softphone;
        this.userAgent = this.voip.userAgent;
        this.state = proxy({
            targetContact: false,
            targetPhoneNumber: "",
        });
        useListener(window, "keydown", this.onWindowKeydown.bind(this));
    }

    /** @returns {string} */
    get activeView() {
        return this.softphone.inCallView.activeView;
    }

    /** @returns {(contact: { id: number }) => boolean} */
    get contactExcludeFilter() {
        const frontId = this.frontSession?.call?.partner_id?.id;
        const backIds = this.props.backSessions.map((session) => session.call?.partner_id?.id);
        const allExcluded = new Set([frontId, ...backIds].filter(Boolean));
        return (contact) => !allExcluded.has(contact.id);
    }

    /** @returns {boolean} */
    get canToggleRecording() {
        return this.frontSession.canToggleRecording;
    }

    /** @returns {import("@voip/core/web/session").Session[]} */
    get displayedBackSessions() {
        if (this.userAgent.hasCallInvitation) {
            const invitationSessionKey = this.userAgent.callInvitationSession.key;
            return Object.values(this.userAgent.sessions)
                .filter((s) => s.key !== invitationSessionKey)
                .reverse();
        }
        if (this.softphone.inCallView.activeView === "default") {
            return this.props.backSessions;
        }
        return [];
    }

    get frontSession() {
        return this.props.frontSession;
    }

    /** @returns {boolean} */
    get isKeypadOpen() {
        return this.softphone.inCallView.keypad.isOpen;
    }

    /** @returns {boolean} */
    get isRecording() {
        return this.frontSession.isRecording;
    }

    /** @returns {ReturnType<_t>} */
    get recordButtonName() {
        return this.isRecording ? _t("Stop") : _t("Record");
    }

    /** @returns {ReturnType<_t>|""} */
    get recordingIndicatorTitle() {
        if (this.voip.config.recordingPolicy === "always") {
            return _t("Enforced by admin");
        }
        return "";
    }

    onClickAddCall() {
        this.softphone.inCallView.activeView = "addCall";
    }

    onClickAddCallContacts() {
        this.softphone.inCallView.addCallView.activeView = "contacts";
    }

    onClickAddCallKeypad() {
        this.softphone.inCallView.addCallView.activeView = "keypad";
    }

    onClickBack() {
        this.softphone.inCallView.activeView = "default";
    }

    onClickHangUp() {
        this.frontSession.hangup();
    }

    onClickHold() {
        this.frontSession.isOnHold = !this.frontSession.isOnHold;
    }

    onClickKeypad() {
        this.softphone.inCallView.keypad.isOpen = !this.isKeypadOpen;
    }

    onClickMute() {
        this.frontSession.isMuted = !this.frontSession.isMuted;
    }

    /** @param {KeyboardEvent} ev */
    onWindowKeydown(ev) {
        const digitMatch = ev.code.match(/^(?:Digit|Numpad)([0-9])$/);
        const key = digitMatch?.[1] || (["*", "#"].includes(ev.key) ? ev.key : null);
        const usesAltGraph = ev.getModifierState("AltGraph");
        if (
            ev.metaKey ||
            ((ev.altKey || ev.ctrlKey) && !usesAltGraph) ||
            ev.repeat ||
            this.activeView !== "default" ||
            !this.frontSession.isOngoing ||
            !key
        ) {
            return;
        }
        const isDtmfInput =
            ev.target.classList?.contains("o-voip-Keypad-input") && this.isKeypadOpen;
        if (isCurrentFocusEditable() && !isDtmfInput) {
            return;
        }
        ev.preventDefault();
        this.softphone.inCallView.keypad.isOpen = true;
        this.frontSession.sendDtmf(key);
        this.softphone.inCallView.keypad.state.input.value += key;
    }

    onClickTransfer() {
        this.softphone.inCallView.activeView = "transfer";
        this.softphone.addressBook.searchInputValue = "";
    }

    onClickConfirmTransfer() {
        this.userAgent.performAttendedTransfer(this.frontSession.key);
    }

    onClickTransferContacts() {
        this.softphone.inCallView.transferView.activeView = "contacts";
    }

    onClickTransferKeypad() {
        this.softphone.inCallView.transferView.activeView = "keypad";
        this.softphone.inCallView.transferView.keypad.input.focus = true;
    }

    onClickTransferPhone() {
        this.state.targetContact = false;
        this.state.targetPhoneNumber =
            this.softphone.inCallView.transferView.keypad.input.value.trim();
        this.softphone.inCallView.transferView.activeView = "confirmation";
    }

    onClickTransferContact(contact) {
        this.state.targetContact = contact;
        this.state.targetPhoneNumber = contact.phone;
        this.softphone.inCallView.transferView.activeView = "confirmation";
    }

    onClickToggleRecording() {
        this.frontSession.toggleRecording();
    }
}
