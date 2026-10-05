import { ActionList } from "@voip/softphone/action_list";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(ActionList.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
    },
    getViewActions() {
        return [...super.getViewActions(), this.getViewSubscriptionsAction()];
    },
    /**
     * Get the view subscriptions action.
     * @returns {Object} Action object
     */
    getViewSubscriptionsAction() {
        return {
            name:
                this.contact?.commercial_partner_subscription_count > 1
                    ? _t("Subscriptions")
                    : _t("Subscription"),
            title:
                this.contact?.commercial_partner_subscription_count > 1
                    ? _t("View subscriptions")
                    : _t("View subscription"),
            icon: "autorenew",
            predicate: () => this.contact?.commercial_partner_subscription_count,
            onClick: async () => {
                const action = await this.orm.call("res.partner", "action_voip_view_subscription", [
                    this.contact.id,
                ]);
                action.target = this.ui.isSmall ? "new" : "current";
                this.action.doAction(action);
            },
        };
    },
});
