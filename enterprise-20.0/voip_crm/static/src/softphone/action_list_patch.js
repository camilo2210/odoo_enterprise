import { ActionList } from "@voip/softphone/action_list";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(ActionList.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
    },
    getCreateActions() {
        return [...super.getCreateActions(), this.getViewLeadsAction("create")];
    },
    getViewActions() {
        return [...super.getViewActions(), this.getViewLeadsAction()];
    },
    /**
     * Get the view leads action.
     * @param {string} type - The action type, either "view" or "create" (default: "view")
     * @returns {Object} Action object
     * @throws {Error} When type is not "view" or "create"
     */
    getViewLeadsAction(type = "view") {
        if (type !== "view" && type !== "create") {
            throw new Error("Invalid type");
        }
        const viewLeadTitle =
            this.contact?.commercial_partner_opportunity_count > 1
                ? _t("View leads")
                : _t("View lead");
        return {
            name: this.contact?.commercial_partner_opportunity_count > 1 ? _t("Leads") : _t("Lead"),
            title: type === "create" ? _t("Create a lead") : viewLeadTitle,
            icon: "star",
            iconClass: "oi-filled",
            predicate: () =>
                this.voip.softphone.shouldShowLeadButton &&
                (type === "view" ? this.contact?.commercial_partner_opportunity_count : true),
            onClick: async () => {
                const phoneNumber = this.phoneNumber;
                const action = await this.orm.call("res.partner", "get_view_opportunities_action", [
                    type === "create" ? false : this.contact?.id,
                    phoneNumber,
                ]);
                if (type === "create") {
                    if (this.contact) {
                        action.context.default_partner_id = this.contact.id;
                    } else {
                        action.context.default_phone = phoneNumber;
                    }
                }
                action.target = this.ui.isSmall ? "new" : "current";
                this.action.doAction(action);
            },
        };
    },
});
