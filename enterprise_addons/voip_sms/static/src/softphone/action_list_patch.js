import { ActionList } from "@voip/softphone/action_list";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(ActionList.prototype, {
    getViewActions() {
        return [...super.getViewActions(), this.getSendSMSAction()];
    },
    /**
     * Get the send SMS action.
     * @param {string} type - The action type, either "view" or "create" (default: "view")
     * @returns {Object} Action object
     * @throws {Error} When type is not "view" or "create"
     */
    getSendSMSAction(type = "view") {
        if (type !== "view" && type !== "create") {
            throw new Error("Invalid type");
        }
        return {
            name: _t("Send SMS"),
            title: _t("Send text message"),
            icon: "chat_bubble",
            iconClass: "oi-filled",
            type: "send",
            onClick: () => {
                const action = {
                    type: "ir.actions.act_window",
                    name: _t("Send text message"),
                    res_model: "sms.composer",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_res_id: this.contact ? this.contact.id : this.props.call?.id,
                        default_res_model: this.contact ? "res.partner" : "voip.call",
                        default_number: this.phoneNumber,
                    },
                };
                this.action.doAction(action);
            },
        };
    },
});
