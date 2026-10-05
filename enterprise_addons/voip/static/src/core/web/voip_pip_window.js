import { Component, proxy, useListener } from "@odoo/owl";
import { ActionButton } from "@voip/softphone/action_button";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { url } from "@web/core/utils/urls";
import { render } from "@web/owl2/utils";

export class VoipPipWindow extends Component {
    static components = { ActionButton };
    static template = "voip.VoipPipWindow";

    setup() {
        this.pipService = useService("voip.pip");
        this.voip = useService("voip");
        this.state = proxy({
            showKeypad: false,
        });
        useListener(this.voip.bus, "session_changed", () => render(this, true));
    }

    get frontSession() {
        return this.voip.userAgent.frontSession;
    }

    get caller() {
        return this.frontSession?.call?.partner_id;
    }

    get callerAvatarUrl() {
        if (!this.caller) {
            return null;
        }
        return url("/web/image", {
            model: "res.partner",
            id: this.caller.id,
            field: "avatar_128",
        });
    }

    get callerName() {
        return this.caller?.voipName || this.frontSession?.phone_number || _t("Unknown");
    }

    get timerText() {
        return this.frontSession?.timerText || "00:00";
    }

    get holdButtonTitle() {
        if (this.frontSession?.isOnHold) {
            return _t("Resume");
        }
        return _t("Hold");
    }

    get muteButtonTitle() {
        if (this.frontSession?.isMuted) {
            return _t("Unmute");
        }
        return _t("Mute");
    }

    get canToggleRecording() {
        return this.voip.config.recordingPolicy === "user" && this.frontSession?.canBeRecorded;
    }

    get isRecording() {
        return Boolean(this.frontSession?.isRecording);
    }

    get recordButtonTitle() {
        return this.isRecording ? _t("Stop") : _t("Record");
    }

    get hangupButtonTitle() {
        return _t("Hang up");
    }

    get keypadButtonTitle() {
        if (this.state.showKeypad) {
            return _t("Hide keypad");
        }
        return _t("Show keypad");
    }

    get keypadKeys() {
        return [
            { key: "1", letters: "" },
            { key: "2", letters: "ABC" },
            { key: "3", letters: "DEF" },
            { key: "4", letters: "GHI" },
            { key: "5", letters: "JKL" },
            { key: "6", letters: "MNO" },
            { key: "7", letters: "PQRS" },
            { key: "8", letters: "TUV" },
            { key: "9", letters: "WXYZ" },
            { key: "*", letters: "", icon: "emergency" },
            { key: "0", letters: "+" },
            { key: "#", letters: "", icon: "tag" },
        ];
    }

    onClickHangup() {
        this.frontSession?.hangup();
    }

    onClickHold() {
        if (!this.frontSession?.isInProgress) {
            return;
        }
        this.frontSession.isOnHold = !this.frontSession.isOnHold;
    }

    onClickMute() {
        if (!this.frontSession?.isInProgress) {
            return;
        }
        this.frontSession.isMuted = !this.frontSession.isMuted;
    }

    onClickToggleKeypad() {
        if (!this.frontSession?.isInProgress) {
            return;
        }
        this.state.showKeypad = !this.state.showKeypad;
        this.pipService.setSize(
            this.state.showKeypad ? this.pipService.sizes.keypad : this.pipService.sizes.compact
        );
    }

    onClickKeypadKey(keyData) {
        if (!this.frontSession?.isInProgress) {
            return;
        }
        const key = keyData?.key;
        if (!key) {
            return;
        }
        this.frontSession.sendDtmf(key);
        const keypadInput = this.voip.softphone.inCallView.keypad.state.input;
        keypadInput.value += key;
        const cursorPosition = keypadInput.value.length;
        Object.assign(keypadInput.selection, {
            start: cursorPosition,
            end: cursorPosition,
            direction: "none",
        });
    }

    onClickRecord() {
        this.frontSession?.toggleRecording();
    }
}
