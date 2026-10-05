import { registry } from "@web/core/registry";
import {
    BadgesSelectionField,
    badgesSelectionField,
} from "@web/views/fields/badges_selection/badges_selection_field";

/** Filter the appointment leave type selection depending on the type of the view,
 * aka if the view displays appointment type(s) scheduled based on users or resources. */
export class AppointmentLeaveTypeBadgesField extends BadgesSelectionField {
    get options() {
        const allOptions = super.options;
        const scheduleBasedOn = this.props.record.context.appointment_schedule_based_on;
        if (scheduleBasedOn === "users") {
            return allOptions.filter(([value]) => value !== "resources");
        }
        if (scheduleBasedOn === "resources") {
            return allOptions.filter(([value]) => value !== "users");
        }
        return allOptions;
    }
}

export const appointmentLeaveTypeBadgesField = {
    ...badgesSelectionField,
    component: AppointmentLeaveTypeBadgesField,
};

registry.category("fields").add("appointment_leave_type_badges", appointmentLeaveTypeBadgesField);
