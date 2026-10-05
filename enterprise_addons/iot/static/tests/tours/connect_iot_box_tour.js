import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("connect_button_with_auto_pair", {
    steps: () =>
        [
            {
                content: "Click on 'Connect' header button",
                trigger: ".o-kanban-button-new:contains('Connect')",
                run: "click",
            },
            {
                content: "Ensure connecting modal is displayed",
                trigger: ".modal-title:contains('IoT Box tour-serial-number found. Connecting...')",
                run: "click",
            },
        ].flat(),
});
