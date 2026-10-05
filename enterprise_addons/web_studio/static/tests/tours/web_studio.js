import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("web_studio_home_menu_background_tour", {
    steps: () => [
        {
            trigger: ".o_home_menu_background",
        },
        {
            trigger: ".o_web_studio_navbar_item",
            content: "Want to customize the background? Let’s activate <b>Odoo Studio</b>.",
            run: "click",
        },
        {
            trigger: ".o_web_studio_change_background",
            content: "Change the <b>background</b>, make it yours.",
            run: "click",
        },
    ],
});
