import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

import { markup } from "@odoo/owl";

registry.category("web_tour.tours").add("timesheet_tour", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            trigger: '.o_app[data-menu-xmlid="hr_timesheet.timesheet_menu_root"]',
            content: markup(
                _t(
                    "<b>Start managing your timesheets</b> <br/> <i>Everything you track begins here.</i>"
                )
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            trigger:
                ".o_grid_view .o_grid_row:not(.o_grid_section).o_grid_cell_today, .o_grid_component_timesheet_uom",
            content: markup(
                _t(
                    "<b>Add time in the Grid view</b> <br/> <i>Click a cell to enter hours. Press Tab or Enter to navigate easily.</i>"
                )
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            id: "open_timesheet_systray",
            trigger: "div.o_menu_systray button.o-dropdown i[data-icon='play_circle']",
            content: markup(
                _t(
                    "<b>Use the timer to track your activities</b> <br/> <i>Start the timer, then log a timesheet when your activity ends. It restarts automatically for the next task.</i>"
                )
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            trigger: "div[name=description_field]",
            content: markup(
                _t(
                    '<b>Add a description</b> <br/> <i>Briefly summarize your activity, e.g., "Metting with the customer."</i>'
                )
            ),
            tooltipPosition: "bottom",
            run: "edit My Activity",
        },
        {
            trigger: "div[name=project_field]",
            content: markup(
                _t(
                    "<b>Select a project</b> <br/> <i>Choose the relevant project, such as a customer or team project.</i>"
                )
            ),
            tooltipPosition: "right",
            run: "click",
        },
        {
            trigger: "button[name=save_btn]",
            content: markup(
                _t(
                    "<b>Create the timesheet</b> <br/> <i>Once saved, the timer automatically restarts for your next activity.</i>"
                )
            ),
            tooltipPosition: "right",
            run: "click",
        },
    ],
});
