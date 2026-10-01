import { Softphone } from "@voip/softphone/softphone_model";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";

patch(Softphone.prototype, {
    shouldShowApplicantButton: false,

    setup() {
        super.setup();
        this.updateApplicationButtonPermission();
    },

    async updateApplicationButtonPermission() {
        this.shouldShowApplicantButton = await user.hasGroup("hr_recruitment.group_hr_recruitment_interviewer");
    },
});
