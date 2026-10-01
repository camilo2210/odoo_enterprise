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
        return [...super.getViewActions(), this.getViewSaleOrderAction()];
    },
    /**
     * Get the view sale order action.
     * @returns {Object} Action object
     */
    getViewSaleOrderAction() {
        return {
            name: this.contact?.commercial_partner_sale_order_count > 1 ? _t("Sales") : _t("Sale"),
            title:
                this.contact?.commercial_partner_sale_order_count > 1
                    ? _t("View sales")
                    : _t("View sale"),
            icon: "attach_money",
            predicate: () => this.contact?.commercial_partner_sale_order_count,
            onClick: async () => {
                const action = await this.orm.call("res.partner", "action_voip_view_sale_orders", [
                    this.contact.id,
                ]);
                action.target = this.ui.isSmall ? "new" : "current";
                this.action.doAction(action);
            },
        };
    },
});
