import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("spreadsheet_share_edit_public", {
    steps: () => [
        {
            trigger: '.o-toolbar-button[title="Bold (Ctrl+B)"]',
            run: "click",
        },
        {
            trigger: '.o-toolbar-button.active[title="Bold (Ctrl+B)"',
            content: "Icon is active",
        },
    ],
});
