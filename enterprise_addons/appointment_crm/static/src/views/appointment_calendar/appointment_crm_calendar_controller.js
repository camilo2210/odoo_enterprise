import { _t } from "@web/core/l10n/translation";
import { markup } from "@odoo/owl";
import { AttendeeCalendarController } from "@calendar/views/attendee_calendar/attendee_calendar_controller";
import { patch } from "@web/core/utils/patch";

patch(AttendeeCalendarController.prototype, {
    /**
     * Add the opportunity name from which the user came from if
     * there is one
     */
    _getOpportunityName() {
        if (!this.props.context.default_opportunity_id) {
            return undefined;
        }
        return this.props.context.default_name;
    },

    _getSelectAvailabilityNotificationMessage() {
        const opportunityName = this._getOpportunityName();
        if (opportunityName) {
            const notificationMessage = _t("Pick meeting time proposals for");
            return markup`${notificationMessage} <i>${opportunityName}</i>.`;
        }
        return super._getSelectAvailabilityNotificationMessage()
    },
});
