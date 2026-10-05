import { models } from "@web/../tests/web_test_helpers";

export class VoipCallLeg extends models.ServerModel {
    _name = "voip.call.leg";

    /**
     * The server materializes one leg per SIP Call-ID, which is how a browser
     * INVITE and the webhook that describes the same channel converge on one
     * call whichever arrives first.
     *
     * @param {number} voipCallId
     * @param {string} sipCallId
     */
    _add_sip_call_id(voipCallId, sipCallId) {
        if (!sipCallId) {
            return;
        }
        const [id] = this.search([["sip_call_id", "=", sipCallId]]);
        if (id === undefined) {
            this.create({ sip_call_id: sipCallId, voip_call_id: voipCallId });
        } else if (!this.browse(id)[0].voip_call_id) {
            this.write([id], { voip_call_id: voipCallId });
        }
    }

    /**
     * @param {string} sipCallId
     * @returns {number|false}
     */
    _find_call_id(sipCallId) {
        if (!sipCallId) {
            return false;
        }
        const [id] = this.search([["sip_call_id", "=", sipCallId]]);
        return id === undefined ? false : this.browse(id)[0].voip_call_id;
    }
}
