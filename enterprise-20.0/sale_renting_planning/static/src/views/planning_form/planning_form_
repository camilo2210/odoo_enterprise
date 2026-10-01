import { PlanningFormController } from "@planning/views/planning_form/planning_form_view";
import { patch } from "@web/core/utils/patch";

patch(PlanningFormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "action_add_last_order" && this.model.root.isNew) {
            clickParams.context = {
                ...(clickParams.context || {}),
                is_rental_shift_new: true,
            }
        }
        return super.beforeExecuteActionButton(clickParams);
    }
})
