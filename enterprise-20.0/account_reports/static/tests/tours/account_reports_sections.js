/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("account_reports_sections", {
    steps: () => [
        {
            content: "Open variant selector",
            trigger: "#filter_variant button",
            run: "click",
        },
        {
            content: "Select the test variant using sections",
            trigger: ".dropdown-item:contains('Test Sections')",
            run: "click",
        },
        {
            content: "Check the lines of section 1 are displayed",
            trigger: ".line_name:contains('Section 1 line')",
        },
        {
            content: "Check the columns of section 1 are displayed",
            trigger: "#table_header th:contains('Column 1')",
        },
        {
            content: "Check the export buttons belong to the composite report",
            trigger: ".btn:contains('composite_report_custom_button')",
        },
        {
            content:
                "Check the filters displayed belong to section 1 (journals filter is not enabled on section 2, nor the composite report)",
            trigger: "#filter_journal",
        },
        {
            content: "Open date switcher",
            trigger: "#filter_date button",
            run: "click",
        },
        {
            content: "Select 'month' date filter",
            trigger: ".dropdown-menu .dropdown-item[data-period-type='month']",
            run: "click",
        },
        {
            content: "Click on the current period to edit it manually",
            trigger: ".dropdown-menu .dropdown-item[data-period-type='month'] .input_current_date",
            run: "click",
        },
        {
            content:
                "Make sure December 2025 is opened, whatever the return type linked to the report",
            trigger: ".dropdown-menu .dropdown-item[data-period-type='month'] .input_current_date",
            run: "edit 12/2025",
        },
        {
            content: "Click outside of the input to validate the choice",
            trigger: ".dropdown-menu .dropdown-item[data-period-type='month']",
            run: "click",
        },
        {
            content: "Wait for the date to be refreshed",
            trigger: `#filter_date button:contains('Dec 2025')`,
        },
        {
            content: "Switch to section 2",
            trigger: "#section_selector .btn:contains('Section 2')",
            run: "click",
        },
        {
            content: "Check the lines of section 2 are displayed",
            trigger: ".line_name:contains('Section 2 line')",
        },
        {
            content: "Check the columns of section 2 are displayed",
            trigger: "#table_header th:contains('Column 2')",
        },
        {
            content: "Check the export buttons belong to the composite report",
            trigger: ".btn:contains('composite_report_custom_button')",
        },
        {
            content:
                "Check the filters displayed belong to section 2 (comparison filter is not enabled on section 1, nor the composite report)",
            trigger: "#filter_comparison",
        },
        {
            content: "Open date switcher",
            trigger: "#filter_date button",
            run: "click",
        },
        {
            content: "Select another date in the future",
            trigger: ".dropdown-menu .dropdown-item[data-period-type='year'] .btn_next_date",
            run: "click",
        },
        {
            content: "Apply filter by closing the dropdown for the future date",
            trigger: "#filter_date .btn:first()",
            run: "click",
        },
        {
            content: "Check that the date has changed",
            trigger: `#filter_date button:not(:contains(2025)):contains(2026)`,
        },
        {
            content: "Open date switcher",
            trigger: "#filter_date button",
            run: "click",
        },
        {
            content: "Select another date first time",
            trigger: ".dropdown-menu .dropdown-item[data-period-type='year'] .btn_previous_date",
            run: "click",
        },
        {
            trigger: `.dropdown-menu .dropdown-item[data-period-type='year'] input[data-value*='2025']`,
        },
        {
            content: "Select another date second time",
            trigger: ".dropdown-menu .dropdown-item[data-period-type='year'] .btn_previous_date",
            run: "click",
        },
        {
            trigger: `.dropdown-menu .dropdown-item[data-period-type='year'] input[data-value*='2024']`,
        },
        {
            content: "Apply filter by closing the dropdown",
            trigger: "#filter_date .btn:first()",
            run: "click",
        },
        {
            content: "Check that the date has changed",
            trigger: `#filter_date button:contains('2024')`,
        },
        {
            content: "Switch back to section 1",
            trigger: "#section_selector .btn:contains('Section 1')",
            run: "click",
        },
    ],
});
