import { Component, t, useProps } from "@odoo/owl";
import { Session } from "@voip/core/web/session";
import { ActionButton } from "@voip/softphone/action_button";
import { ActionList } from "@voip/softphone/action_list";
import { ContactInfo } from "@voip/softphone/contact_info";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

const { TIME_SIMPLE } = luxon.DateTime;

export class CallSummary extends Component {
    static components = { ActionButton, ActionList, ContactInfo };
    static template = "voip.CallSummary";

    props = useProps({
        session: t.instanceOf(Session),
    });

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        const voip = useService("voip");
        this.userAgent = voip.userAgent;
        this.softphone = voip.softphone;
    }

    /** @returns {import("@voip/core/web/session").Session} */
    get session() {
        return this.props.session;
    }

    /** @returns {string} */
    get statusText() {
        const date = this.session.createDate;
        const time = date.toLocaleString(TIME_SIMPLE);
        switch (this.session.status) {
            case "aborted":
                return _t("Call cancelled (%(time)s)", { time });
            case "missed":
                return _t("Call Missed (%(time)s)", { time });
            case "rejected":
                return _t("Call declined (%(time)s)", { time });
            case "completed_elsewhere":
                return _t("Call completed elsewhere (%(time)s)", { time });
            case "terminated":
                return _t("Lasted: %(duration)s", { duration: this.session.timerText });
            default:
                return "✌︎☹︎☹︎☜︎💧︎ ✋︎💧︎ 😐︎✌︎🏱︎⚐︎❄︎";
        }
    }

    /** @param {MouseEvent} ev */
    onClickCall(ev) {
        this.userAgent.makeCall({
            partner: this.session.call?.partner_id,
            phone_number: this.session.displayedPhoneNumber,
        });
    }
}
