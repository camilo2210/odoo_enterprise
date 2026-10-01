import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import "@timesheet_grid/js/tours/timesheet_grid";
import { patch } from "@web/core/utils/patch";
import { markup } from "@odoo/owl";

patch(registry.category("web_tour.tours").get("timesheet_tour"), {
    steps() {
        const originalSteps = super.steps();
        const stepIndex = originalSteps.findIndex(
            (step) => step.id === "open_timesheet_systray"
        );

        if (stepIndex !== -1) {
            const dangerCircle = "div.o_menu_systray button.o-dropdown > i[data-icon='circle'].text-danger";
            const successCircle = "div.o_menu_systray button.o-dropdown > i[data-icon='circle'].text-success";
            const conditionalSteps = [
                {
                    trigger: `${dangerCircle}, ${successCircle}`,
                    content: markup(_t("<b>Use the timer to track your time</b> <br/> <i>Start your day by checking in and log timesheets from anywhere.</i>")),
                    run: "click",
                },
                {
                    isActive: [dangerCircle],
                    trigger: "div.o_wrap_btn_sign_out button.btn-primary",
                    content: markup(_t("<b>Check in to start the timer</b> <br/> <i>This begins tracking your current activity automatically.</i>")),
                    run: "click",
                },
            ];

            originalSteps.splice(stepIndex, 1, ...conditionalSteps);
        }

        return originalSteps;
    },
});
