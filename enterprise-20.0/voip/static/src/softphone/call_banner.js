import { Component, t, useProps } from "@odoo/owl";
import { Session } from "@voip/core/web/session";
import { ActionButton } from "@voip/softphone/action_button";
import { useService } from "@web/core/utils/hooks";

export class CallBanner extends Component {
    static components = { ActionButton };
    static template = "voip.CallBanner";

    props = useProps({
        backSession: t.instanceOf(Session),
        isFirst: t.boolean().optional(),
    });

    setup() {
        const voip = useService("voip");
        this.userAgent = voip.userAgent;
    }

    get backSession() {
        return this.props.backSession;
    }

    get contactName() {
        return (
            this.backSession.alias ||
            this.backSession.call?.partner_id?.voipName ||
            this.backSession.displayedPhoneNumber ||
            ""
        );
    }

    onClickHangUp() {
        this.backSession.hangup();
    }

    onClickSwitchCall() {
        this.userAgent.promoteToFront(this.backSession.key);
    }
}
