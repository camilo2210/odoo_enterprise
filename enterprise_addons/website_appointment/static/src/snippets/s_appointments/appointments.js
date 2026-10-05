import { registry } from "@web/core/registry";
import { DynamicSnippet } from "@website/snippets/s_dynamic_snippet/dynamic_snippet";
import { AppointmentsMixin } from "./appointments_mixin";

const AppointmentsBase = AppointmentsMixin(DynamicSnippet);

export class AppointmentsListSnippet extends AppointmentsBase {
    static selector = ".s_appointments:not(.s_appointments_carousel)";
}

registry.category("public.interactions.edit").add("website_appointment.appointments_base", {
    Interaction: AppointmentsBase,
    isAbstract: true,
});

registry.category("public.interactions").add("website_appointment.appointments", AppointmentsListSnippet);

registry
    .category("public.interactions.edit")
    .add("website_appointment.appointments", {
        Interaction: AppointmentsListSnippet,
    });

registry
    .category("public.interactions.preview")
    .add("website_appointment.appointments", {
        Interaction: AppointmentsListSnippet,
    });
