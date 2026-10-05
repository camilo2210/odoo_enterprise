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
        return [...super.getCreateActions(), this.getViewTicketsAction("create")];
    },
    getViewActions() {
        return [...super.getViewActions(), this.getViewTicketsAction()];
    },
    /**
     * Get the view tickets action.
     * @param {string} type - The action type, either "view" or "create" (default: "view")
     * @returns {Object} Action object
     * @throws {Error} When type is not "view" or "create"
     */
    getViewTicketsAction(type = "view") {
        if (type !== "view" && type !== "create") {
            throw new Error("Invalid type");
        }
        const viewTicketTitle =
            this.contact?.commercial_partner_ticket_count > 1
                ? _t("View tickets")
                : _t("View ticket");
        const createTicketAction = {
            type: "ir.actions.act_window",
            name: _t("Create a ticket"),
            res_model: "helpdesk.ticket",
            views: [[false, "form"]],
            context: {},
        };
        const isTicketButtonVisible =
            type === "view" ? this.contact?.commercial_partner_ticket_count : true;
        return {
            name: this.contact?.commercial_partner_ticket_count > 1 ? _t("Tickets") : _t("Ticket"),
            title: type === "create" ? _t("Create a ticket") : viewTicketTitle,
            icon: "support",
            predicate: () => this.voip.softphone.shouldShowTicketButton && isTicketButtonVisible,
            onClick: async () => {
                const action =
                    type === "view"
                        ? await this.orm.call("res.partner", "action_voip_open_tickets", [
                              this.contact.id,
                          ])
                        : createTicketAction;
                action.target = this.ui.isSmall ? "new" : "current";
                if (type === "create") {
                    if (this.contact) {
                        action.context.default_partner_id = this.contact.id;
                    } else {
                        action.context.default_partner_phone = this.phoneNumber;
                    }
                }
                this.action.doAction(action);
            },
        };
    },
});
