import { Component, t, useProps } from "@odoo/owl";
import { Session } from "@voip/core/web/session";
import { ActionButton } from "@voip/softphone/action_button";
import { ActionList } from "@voip/softphone/action_list";
import { ContactInfo } from "@voip/softphone/contact_info";

/**
 * Incoming call screen. Displays information about the caller, along with a
 * series of actions, and buttons to accept or reject the call.
 */
export class CallInvitation extends Component {
    static components = { ActionButton, ActionList, ContactInfo };
    static template = "voip.CallInvitation";

    props = useProps({
        callInvitationSession: t.instanceOf(Session),
    });

    get callInvitationSession() {
        return this.props.callInvitationSession;
    }

    /** @param {MouseEvent} ev */
    onClickAccept(ev) {
        this.callInvitationSession.accept();
    }

    /** @param {MouseEvent} ev */
    onClickReject(ev) {
        this.callInvitationSession.reject();
    }
}
