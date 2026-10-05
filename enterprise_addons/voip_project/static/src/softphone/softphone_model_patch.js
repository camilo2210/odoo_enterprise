import { Softphone } from "@voip/softphone/softphone_model";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";

patch(Softphone.prototype, {
    shouldShowLeadButton: false,

    setup() {
        super.setup();
        this.updateTaskButtonPermissions();
    },

    async updateTaskButtonPermissions() {
        this.shouldShowTaskButton = await user.hasGroup("project.group_project_user");
    },
});
