import { registry } from "@web/core/registry";
import { AppointmentsOption } from "./appointments_option";

export class AppointmentsCarouselOption extends AppointmentsOption {
    static id = "appointments_carousel_option";
    static template = "website_appointment.AppointmentsCarouselOption";
}

registry.category("website-options").add(AppointmentsCarouselOption.id, AppointmentsCarouselOption);
