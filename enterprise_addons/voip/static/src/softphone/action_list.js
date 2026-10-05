import { Component, t, useProps } from "@odoo/owl";
import { Call } from "@voip/core/common/call_model";
import { Session } from "@voip/core/web/session";
import { ActionButton } from "@voip/softphone/action_button";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

/**
 * This component is used to display the actions for the tab entry in the softphone.
 */
export class ActionList extends Component {
    static components = { ActionButton, Dropdown, DropdownItem };
    static template = "voip.ActionList";

    props = useProps({
        activity: t.object().optional(),
        call: t.instanceOf(Call).optional(),
        session: t.instanceOf(Session).optional(),
        contact: t.object().optional(),
    });

    setup() {
        this.action = useService("action");
        this.ui = useService("ui");
        this.voip = useService("voip");
        this.createActionsDropdownState = useDropdownState();
        this.viewActionsDropdownState = useDropdownState();
    }

    get call() {
        return this.props.call || this.props.session?.call;
    }

    get contact() {
        if (this.props.activity) {
            return this.props.activity.partner;
        }
        if (this.call) {
            return this.call.partner_id;
        }
        return this.props.contact;
    }

    get phoneNumber() {
        return this.call?.phone_number || this.props.session?.phone_number || this.contact?.phone;
    }

    /**
     * Get filtered actions for a specific category.
     * @param {string} category - The action category, either "create" or "view"
     * @returns {Array} Array of action objects that pass their predicate filters
     * @throws {Error} When category is not "create" or "view"
     */
    getActions(category) {
        if (category !== "create" && category !== "view") {
            throw new Error("Invalid category");
        }
        const actions = category === "create" ? this.getCreateActions() : this.getViewActions();
        return actions.filter((action) => {
            if (action.predicate) {
                return action.predicate();
            }
            return true;
        });
    }

    /**
     * Get all available create actions.
     * To be overridden by patches to add new actions.
     * @returns {Array} Array of action objects
     */
    getCreateActions() {
        return [this.getViewContactAction("create")];
    }

    /**
     * Get the send email action.
     * @returns {Object} Action object
     */
    getSendEmailAction() {
        return {
            name: _t("Send Email"),
            title: _t("Send an e-mail"),
            icon: "mail",
            type: "send",
            predicate: () => this.contact?.email,
            onClick: () => {
                this.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "mail.compose.message",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_res_ids: [this.contact.id],
                        default_model: "res.partner",
                        default_partner_ids: [this.contact.id],
                        default_composition_mode: "comment",
                        default_use_template: true,
                    },
                });
            },
        };
    }

    /**
     * Get the view call action.
     * @returns {Object} Action object
     */
    getViewCallAction() {
        return {
            name: _t("Call details"),
            title: _t("View call details"),
            icon: "east",
            type: "view",
            predicate: () => this.call && this.voip.softphone.activeTab === "recent",
            onClick: () => {
                this.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "voip.call",
                    res_id: this.call.id,
                    target: this.ui.isSmall ? "new" : "current",
                    views: [[false, "form"]],
                });
            },
        };
    }

    /**
     * Get the view activity action.
     * @returns {Object} Action object
     */
    getViewActivityAction() {
        return {
            name: _t("Activity details"),
            title: _t("View activity details"),
            icon: "east",
            type: "view",
            predicate: () => this.voip.softphone.activeTab === "activities",
            onClick: () => {
                this.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: this.props.activity.res_model,
                    res_id: this.props.activity.res_id,
                    views: [[false, "form"]],
                    target: this.ui.isSmall ? "new" : "current",
                });
            },
        };
    }

    /**
     * Get all available view actions.
     * To be overridden by patches to add new actions.
     * @returns {Array} Array of action objects
     */
    getViewActions() {
        return [
            this.getViewCallAction(),
            this.getViewActivityAction(),
            this.getViewContactAction(),
            this.getSendEmailAction(),
        ];
    }

    /**
     * Get the view contact action.
     * @param {string} type - The action type, either "view" or "create" (default: "view")
     * @returns {Object} Action object
     */
    getViewContactAction(type = "view") {
        if (type !== "view" && type !== "create") {
            throw new Error("Invalid type");
        }
        return {
            name: _t("Contact"),
            title: type === "view" ? _t("View customer details") : _t("Create a new contact"),
            icon: "person",
            iconClass: "oi-filled",
            predicate: () => (type === "view" ? this.contact : !this.contact),
            onClick: () => {
                const action = {
                    type: "ir.actions.act_window",
                    res_model: "res.partner",
                    views: [[false, "form"]],
                    target: this.ui.isSmall ? "new" : "current",
                    context: {},
                };
                if (type === "view") {
                    action.res_id = this.contact.id;
                } else {
                    action.context.default_phone = this.phoneNumber;
                }
                this.action.doAction(action);
            },
        };
    }
}
