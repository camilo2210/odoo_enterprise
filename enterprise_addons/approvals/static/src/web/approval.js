import { propSignal } from "@mail/utils/common/hooks";

import { Component, computed, useProps, t } from "@odoo/owl";

import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

export class Approval extends Component {
    static template = "approvals.Approval";

    setup() {
        super.setup(...arguments);
        this.store = useService("mail.store");
        this.activity = propSignal("activity", t.instanceOf(this.store["mail.activity"]));
        this.onChange = useProps.static("onChange", t.function([]));
        this.isApprover = computed(() => user.userId == this.activity().approver_id.user_id);
    }

    async onClickApprove() {
        const activity = this.activity();
        await this.env.services.orm.call("approval.approver", "action_approve", [
            activity.approver_id.id,
        ]);
        activity.remove();
        this.onChange();
    }

    async onClickRefuse() {
        const activity = this.activity();
        await this.env.services.orm.call("approval.approver", "action_refuse", [
            activity.approver_id.id,
        ]);
        activity.remove();
        this.onChange();
    }
}
