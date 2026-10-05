import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("account_reports_widgets", {
    steps: () => [
        {
            content: "change date filter",
            trigger: "#filter_date button",
            run: "click",
        },
        {
            content: "Select another date in the future",
            trigger: ".dropdown-menu .dropdown-item:nth-child(3) .btn_next_date",
            run: "click",
        },
        {
            content: "Apply filter by closing the dropdown",
            trigger: "#filter_date .btn:first()",
            run: "click",
        },
        {
            content: "wait refresh",
            trigger: `#filter_date button:not(:contains(${new Date().getFullYear()}))`,
        },
        {
            content: "change date filter for the second time",
            trigger: "#filter_date button",
            run: "click",
        },
        {
            content: "Select another date in the past first time",
            trigger: ".dropdown-menu .dropdown-item:nth-child(3) .btn_previous_date",
            run: "click",
        },
        {
            trigger: `.dropdown-menu .dropdown-item:nth-child(3) input[data-value*='${new Date().getFullYear()}']`,
        },
        {
            content: "Select another date in the past second time",
            trigger: ".dropdown-menu .dropdown-item:nth-child(3) .btn_previous_date",
            run: "click",
        },
        {
            trigger: `.dropdown-menu .dropdown-item:nth-child(3) input[data-value*='${
                new Date().getFullYear() - 1
            }']`,
        },
        {
            content: "Apply filter by closing the dropdown",
            trigger: "#filter_date .btn:first()",
            run: "click",
        },
        {
            content: "wait refresh",
            trigger: `#filter_date button:contains(${new Date().getFullYear() - 1})`,
        },
        {
            content: "change comparison filter",
            trigger: "#filter_comparison .btn:first()",
            run: "click",
        },
        {
            content: "select custom comparison dates",
            trigger: "[name='filter_comparison_custom']",
            run: "click",
        },
        {
            content: "Apply filter by closing the dropdown",
            trigger: "#filter_comparison .btn:first()",
            run: "click",
        },
        {
            content: "wait refresh, report should have comparison columns",
            trigger: "th + th + th + th",
        },
        {
            content: "Open actions dropdown",
            trigger: ".o_control_panel_breadcrumbs_actions .dropdown-toggle",
            run: "click",
        },
        {
            content: "Export XLSX",
            trigger: ".dropdown-item:contains('XLSX')",
            run: "click",
        },
    ],
});
