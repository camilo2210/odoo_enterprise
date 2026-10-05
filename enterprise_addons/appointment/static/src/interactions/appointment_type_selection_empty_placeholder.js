import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class AppointmentTypeSelectionEmptyPlaceholder extends Interaction {
    static selector = ".o_appointment_selection";
    dynamicContent = {
        ".o_appointment_not_found > div": {
            "t-att-class": () => ({
                "d-none": false,
            }),
        },
    };

    start() {
        // Load an image when no appointment types are found
        // TODO: maybe define a "replace" position in renderAt
        const el = this.el.querySelector(".o_appointment_svg i");
        if (el) {
            this.renderAt("Appointment.appointment_svg", {}, el, "afterend");
            el.remove();
        }
    }
}

registry
    .category("public.interactions")
    .add("appointment.appointment_type_selection_empty_placeholder", AppointmentTypeSelectionEmptyPlaceholder);
