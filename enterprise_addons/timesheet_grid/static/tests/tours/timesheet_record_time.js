import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("timesheet_overtime_hour_encoding", {
    steps: () => [
        {
            trigger: ".o_app[data-menu-xmlid='hr_timesheet.timesheet_menu_root']",
            content: "Open Timesheet app.",
            run: "click",
        },
        {
            trigger: "button.btn.btn-secondary span[title='Previous']",
            run: "click",
        },
        {
            trigger:
                ".o_grid_bar_chart_overtime[title='Total overtime']:contains('+5h'):not(:visible)",
            run: "hover",
        },
        {
            trigger: ".o_grid_row",
            run: async function () {
                const expectedValues = ["+2h", "+1h", "-1h", "-2h", "-3h"];
                document
                    .querySelectorAll(".o_grid_bar_chart_overtime[title='Daily overtime']")
                    .forEach((span, index) => {
                        if (span.textContent.trim() !== expectedValues[index]) {
                            throw new Error(
                                `Tour stopped: Expected ${
                                    expectedValues[index]
                                }, but found ${span.textContent.trim()}`
                            );
                        }
                    });
            },
        },
    ],
});

registry.category("web_tour.tours").add("timesheet_overtime_day_encoding", {
    steps: () => [
        {
            trigger: ".o_app[data-menu-xmlid='hr_timesheet.timesheet_menu_root']",
            content: "Open Timesheet app.",
            run: "click",
        },
        {
            trigger: "button.btn.btn-secondary span[title='Previous']",
            run: "click",
        },
        {
            trigger:
                ".o_grid_bar_chart_overtime[title='Total overtime']:contains('-0.50'):not(:visible)",
            run: "hover",
        },
        {
            trigger: ".o_grid_row",
            run: async function () {
                const expectedValues = ["+0.25", "-0.13", "-0.25", "-0.38"];
                document
                    .querySelectorAll(".o_grid_bar_chart_overtime[title='Daily overtime']")
                    .forEach((span, index) => {
                        if (span.textContent.trim() !== expectedValues[index]) {
                            throw new Error(
                                `Tour stopped: Expected ${
                                    expectedValues[index]
                                }, but found ${span.textContent.trim()}`
                            );
                        }
                    });
            },
        },
    ],
});
