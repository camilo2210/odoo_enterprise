/** @odoo-module **/
import { Component, t, useProps } from "@odoo/owl";
import { toNotifications } from "@l10n_ch_hr_payroll/components/swissdec_format";

const ALERTS = {
    error: { className: "alert-danger", icon: "cancel", iconClass: "oi-filled" },
    warning: { className: "alert-warning", icon: "warning", iconClass: "" },
    info: { className: "alert-info", icon: "info", iconClass: "" },
};

export class SwissdecNotification extends Component {
    static template = "l10n_ch_hr_payroll.SwissdecNotification";
    props = useProps({
        type: t.string(), // "error", "warning" or "info"
        notifications: t.or([t.array(), t.object()]).optional(),
    });

    get alert() {
        return ALERTS[this.props.type] || ALERTS.info;
    }

    get notifications() {
        return toNotifications(this.props.notifications, this.props.type);
    }
}

export default SwissdecNotification;
