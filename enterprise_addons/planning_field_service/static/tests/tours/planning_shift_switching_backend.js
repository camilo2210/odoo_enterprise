import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import "@planning/../tests/tours/planning_tests_tours";

patch(registry.category("web_tour.tours").get("planning_shift_switching_backend"), {
    steps() {
        const originalSteps = super.steps();
        const clickActionSwitchShiftStep = originalSteps.findIndex(
            (step) => step.id === "click_action_switch_shift"
        );
        originalSteps.splice(clickActionSwitchShiftStep + 1, 0, {
            trigger: ".breadcrumb-item.o_back_button",
            content: "Go back to the kanban view",
            run: "click",
        });
        const closeFormInGanttStep = originalSteps.findIndex(
            (step) => step.id === "close_form_in_gantt"
        );
        originalSteps.splice(closeFormInGanttStep, 1, {
            trigger: ".breadcrumb-item.o_back_button",
            content: "Go back to the kanban view",
            run: "click",
        });
        return originalSteps;
    },
});
