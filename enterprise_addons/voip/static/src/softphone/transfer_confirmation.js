import { Component, t, useProps } from "@odoo/owl";
import { Session } from "@voip/core/web/session";
import { ActionButton } from "@voip/softphone/action_button";
import { ContactInfo } from "@voip/softphone/contact_info";
import { useService } from "@web/core/utils/hooks";

export class TransferConfirmation extends Component {
    static components = { ActionButton, ContactInfo };
    static template = "voip.TransferConfirmation";

    props = useProps({
        frontSession: t.instanceOf(Session),
        targetContact: t.or([t.object(), t.boolean()]),
        targetPhoneNumber: t.string(),
    });

    setup() {
        const voip = useService("voip");
        this.userAgent = voip.userAgent;
        this.softphone = voip.softphone;
    }

    get frontSession() {
        return this.props.frontSession;
    }

    onClickDirectTransfer() {
        this.softphone.addressBook.searchInputValue = "";
        this.userAgent.blindTransfer(this.frontSession.key, this.props.targetPhoneNumber);
    }

    async onClickAskFirst() {
        await this.userAgent.makeCall(
            {
                phone_number: this.props.targetPhoneNumber,
                partner: this.props.targetContact,
            },
            {
                transferFromSessionKey: this.frontSession.key,
            }
        );
        this.softphone.inCallView.transferView.activeView = "contacts";
    }
}
