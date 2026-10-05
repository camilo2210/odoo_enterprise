import { formatDate, deserializeDate } from "@web/core/l10n/dates";
import { Dialog } from "@web/core/dialog/dialog";
import { user } from "@web/core/user";

import { Component, computed, proxy, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { sortBy } from "@web/core/utils/arrays";

export class StudioApprovalInfos extends Component {
    static template = "StudioApprovalInfos";
    static components = { Dialog };
    props = useProps({
        isPopover: t.boolean(),
        approval: t.object(),
        close: t.function().optional(),
    });

    ruleIdToEntry = computed(() =>
        Object.fromEntries(this.state.entries.map((e) => [e.rule_id[0], e]))
    );

    canRevokeByRuleId = computed(() => {
        let ruleGrouped = Object.groupBy(
            Object.values(this.props.approval.rules),
            (rule) => rule.notification_order
        );

        ruleGrouped = sortBy(Object.entries(ruleGrouped), ([key]) => parseInt(key), "desc");

        const result = {};

        let canRevoke = false;
        for (const group of ruleGrouped) {
            const localCanRevoke = canRevoke;
            group[1].forEach((rule) => {
                result[rule.id] = localCanRevoke;
                canRevoke ||= rule.can_validate;
            });
        }

        return result;
    });

    setup() {
        this.user = user;
        const approval = this.props.approval;
        this.approval = approval;
        this.state = proxy(approval.state);
        this.actionService = useService("action");
        this.uiService = useService("ui");
    }

    formatDate(val, format) {
        return formatDate(deserializeDate(val), { format });
    }

    getEntry(ruleId) {
        return this.ruleIdToEntry()[ruleId];
    }

    setApproval(ruleId, approved) {
        return this.approval.setApproval(ruleId, approved);
    }

    canRevokeEntry(ruleId) {
        const entry = this.getEntry(ruleId);
        return entry.user_id[0] === this.user.userId || this.canRevokeByRuleId()[ruleId];
    }

    cancelApproval(ruleId) {
        return this.approval.cancelApproval(ruleId);
    }

    openKanbanApprovalRules() {
        const { resModel, method, action } = this.approval;
        return this.actionService.doActionButton({
            type: "object",
            name: "open_kanban_rules",
            resModel: "studio.approval.rule",
            resIds: [],
            args: JSON.stringify([resModel, method, action]),
        });
    }
}
