import { registry } from "@web/core/registry";
import { BadgeField, badgeField } from "@web/views/fields/badge/badge_field";

export class PosAppointmentBadgeField extends BadgeField {
    static template = "pos_appointment.PosAppointmentBadgeField";
}

registry.category("fields").add("pos_appointment_badge", {
    ...badgeField,
    component: PosAppointmentBadgeField,
});
