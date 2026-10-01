import { Call } from "@voip/core/common/call_model";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { BadgeField } from "@web/views/fields/badge/badge_field";

export class CallStatusBadgeField extends BadgeField {
    static template = "voip.CallStatusBadgeField";

    setup() {
        super.setup();
        const voip = useService("voip");
        this.userAgent = voip.userAgent;
    }

    /** @returns {string} */
    get icon() {
        const direction = this.props.record.data.direction;
        if (direction === "outgoing") {
            return "north_east";
        }
        if (direction === "incoming") {
            return "south_west";
        }
        return "";
    }

    isInProgress(call) {
        return this.userAgent.isInProgress(call);
    }

    /** @returns {ReturnType<_t>} */
    get statusLabel() {
        const call = { id: this.props.record.resId, ...this.props.record.data };
        const { state } = call;
        const isInProgress = this.isInProgress(call);
        return Call.getStatus({ isInProgress, state });
    }

    /** @returns {ReturnType<_t>} */
    get statusTooltip() {
        const call = { id: this.props.record.resId, ...this.props.record.data };
        let { state } = call;
        if (["calling", "ongoing"].includes(state) && !this.isInProgress(call)) {
            state = "ended_unexpectedly";
        }
        switch (state) {
            case "aborted":
                return _t("The caller ended the call before pickup.");
            case "calling":
                return _t("The callee's phone is ringing right now.");
            case "completed_elsewhere":
                return _t("The call was answered on another device.");
            case "ended_unexpectedly":
                return _t("Call ended for another reason than a hangup.");
            case "missed":
                return _t("The callee did not pick up.");
            case "ongoing":
                return _t("Both parties are in the call right now.");
            case "rejected":
                return _t("The callee pressed the hangup key while ringing.");
            case "terminated":
                return _t("The call ended successfully.");
            default:
                return "";
        }
    }

    /** @returns {string} */
    get badgeClass() {
        const state = this.props.record.data.state;
        if (state === "rejected" || state === "missed") {
            return "text-bg-danger";
        }
        if (state === "aborted") {
            return "text-bg-secondary";
        }
        if (state === "calling" || state === "ongoing" || state === "ended_unexpectedly") {
            return "text-bg-warning";
        }
        return "text-bg-success";
    }
}

registry.category("fields").add("voip_call_status_badge", {
    component: CallStatusBadgeField,
    displayName: _t("Call Status Badge"),
    supportedTypes: ["char", "selection"],
});
