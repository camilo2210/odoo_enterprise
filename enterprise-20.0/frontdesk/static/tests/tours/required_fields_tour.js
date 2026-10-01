import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("required_fields_tour", {
    steps: () => [
        {
            content: "Filling the details",
            trigger: "input#company",
            run: "edit Office",
        },
        {
            content: "Filling the details",
            trigger: "input#name",
            run: "edit Test_Tour_2",
        },
        {
            content: "Filling the details",
            trigger: "input#phone",
            run: "edit 1234567890",
        },
        {
            content: "Filling the details",
            trigger: "input#email",
            run: "edit test@example.com",
        },
        {
            content: "Click on Browse All Hosts button",
            trigger: ".btn:contains('Browse All Hosts')",
            run: "click",
        },
        {
            content: "Search for host in manual selection",
            trigger: 'input[placeholder="Search..."]',
            run: "edit Test",
        },
        {
            content: "Select the host from the card list",
            trigger: 'h6:contains("Test Host Employee")',
            run: "click",
        },
        {
            content: "Click on the Continue button",
            trigger: ".btn:contains('Continue')",
            run: "click",
        },
        {
            content: "Check that we reached on the last page",
            trigger: "h1:contains('You have been registered!')",
        },
    ],
});
