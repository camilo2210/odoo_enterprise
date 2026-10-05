import { Component, t, useProps } from "@odoo/owl";

import { ActionButton } from "@voip/softphone/action_button";
import { Keypad } from "@voip/softphone/keypad";
import { KeypadModel } from "@voip/softphone/keypad_model";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class Dialer extends Component {
    static components = { ActionButton, Keypad };
    static template = "voip.Dialer";

    props = useProps({
        onClickBack: t.function().optional(),
        state: t.instanceOf(KeypadModel),
    });

    setup() {
        this.voip = useService("voip");
        this.userAgent = this.voip.userAgent;
        this.softphone = this.voip.softphone;
        this.props.state.input.focus = true;
    }

    async getLastOutgoingCall() {
        const ids = await this.voip.fetchRecentCalls({ limit: 1, direction: "outgoing" });
        return this.voip.store["voip.call"].get(ids[0]);
    }

    onCallVoicemail() {
        const voicemailCode = this.voip.config.voicemailCode;
        if (voicemailCode) {
            this._makeCall(
                { phone_number: voicemailCode, alias: _t("Mailbox") },
                { usePrefill: false }
            );
        }
    }

    /** @param {MouseEvent} ev */
    async onClickCall(ev) {
        const inputValue = this.props.state.input.value.trim();
        if (inputValue) {
            const callData = { phone_number: inputValue };
            await this._makeCall(callData, { resetInCallView: true });
            return;
        }
        this.voip.invalidatePrefill();
        const lastOutgoingCall = await this.getLastOutgoingCall();
        if (!lastOutgoingCall) {
            return;
        }
        this.props.state.input.value = lastOutgoingCall.phone_number;
        this.props.state.input.country = lastOutgoingCall.phone_country_id;
    }

    async onClickKeypadContact(contact) {
        const callData = { partner: contact, phone_number: contact.phone };
        await this._makeCall(callData, {
            usePrefill: this.props.state.prefillContext?.partnerId === contact.id,
        });
    }

    async _makeCall(callData, { usePrefill = true, resetInCallView = false } = {}) {
        const usedPrefill = usePrefill && this._applyPrefillContext(callData);
        let prefillConsumed = false;
        const consumePrefill = () => {
            if (usedPrefill && !prefillConsumed) {
                prefillConsumed = true;
                this.voip.invalidatePrefill();
            }
        };
        this.voip.invalidatePrefill({ clearContext: !usedPrefill });
        const callMade = await this.userAgent.makeCall(callData, {
            onCallRecordCreationStarted: consumePrefill,
        });
        if (callMade) {
            // TODO this should probably not be an option and always be part of
            // userAgent.makeCall, it will be investigated later.
            if (resetInCallView) {
                this.softphone.inCallView.reset();
            }
            consumePrefill();
        }
    }

    /**
     * Attaches the prefill record context (res_model/res_id) to the call data.
     * @param {Object} callData
     * @returns {boolean} whether the prefill context was attached
     */
    _applyPrefillContext(callData) {
        const ctx = this.props.state.prefillContext;
        if (!ctx) {
            return false;
        }
        callData.res_id ??= ctx.resId;
        callData.res_model ??= ctx.resModel;
        return true;
    }

    onClickContactHistory(contact) {
        this.softphone.openContactHistory(contact, { previousTab: "dialer" });
    }
}
