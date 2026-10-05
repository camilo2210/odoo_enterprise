import { Softphone } from "@voip/softphone/softphone_model";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";

patch(Softphone.prototype, {
    shouldShowTicketButton: false,

    setup() {
        super.setup();
        this.updateTicketButtonPermission();
    },

    async updateTicketButtonPermission() {
        this.shouldShowTicketButton = await user.hasGroup("helpdesk.group_helpdesk_user");
    },
});
