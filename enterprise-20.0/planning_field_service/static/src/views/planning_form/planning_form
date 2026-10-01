import { PlanningFormController } from "@planning/views/planning_form/planning_form_view";
import { user } from "@web/core/user";

import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(PlanningFormController.prototype, {
    setup() {
        super.setup();
        this.fieldServiceGeolocation = useService("field_service_geolocation");
        this.allowGeolocation = false;
    },
    async beforeExecuteActionButton(clickParams) {
        if (
            ["action_sign_in", "action_complete"].includes(clickParams.name) &&
            this.model.root.data.user_ids.resIds.includes(user.userId)
        ) {
            this.fieldServiceGeolocation.startWatch();
            clickParams.context = {
                ...(clickParams.context || {}),
                geolocation: await this.fieldServiceGeolocation.getGeolocation(),
            };
        }
        return super.beforeExecuteActionButton(clickParams);
    },
});
