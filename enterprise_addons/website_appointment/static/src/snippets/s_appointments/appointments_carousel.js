import { registry } from "@web/core/registry";
import { DynamicSnippetCarousel } from "@website/snippets/s_dynamic_snippet_carousel/dynamic_snippet_carousel";
import { AppointmentsMixin } from "./appointments_mixin";

const AppointmentsCarouselBase = AppointmentsMixin(DynamicSnippetCarousel);

export class AppointmentsCarousel extends AppointmentsCarouselBase {
    static selector = ".s_appointments_carousel";
}

registry
    .category("public.interactions.edit")
    .add("website_appointment.appointments_carousel_base", {
        Interaction: AppointmentsCarouselBase,
        isAbstract: true,
    });

registry
    .category("public.interactions")
    .add("website_appointment.appointments_carousel", AppointmentsCarousel);

registry.category("public.interactions.edit").add("website_appointment.appointments_carousel", {
    Interaction: AppointmentsCarousel,
});
