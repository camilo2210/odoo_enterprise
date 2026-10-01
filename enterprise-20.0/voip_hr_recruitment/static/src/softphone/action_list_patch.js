import { ActionList } from "@voip/softphone/action_list";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(ActionList.prototype, {
    getCreateActions() {
        return [...super.getCreateActions(), this.getViewApplicantsAction("create")];
    },
    getViewActions() {
        return [...super.getViewActions(), this.getViewApplicantsAction()];
    },
    /**
     * Get the view applicants action.
     * @param {string} type - The action type, either "view" or "create" (default: "view")
     * @returns {Object} Action object
     * @throws {Error} When type is not "view" or "create"
     */
    getViewApplicantsAction(type = "view") {
        if (type !== "view" && type !== "create") {
            throw new Error("Invalid type");
        }
        const viewApplicantTitle =
            this.contact?.applicant_ids?.length > 1 ? _t("View applicants") : _t("View applicant");
        const isApplicantButtonVisible =
            type === "view"
                ? this.contact?.applicant_ids?.length
                : !this.contact?.applicant_ids?.length;
        return {
            name: this.contact?.applicant_ids?.length > 1 ? _t("Applicants") : _t("Applicant"),
            title: !this.contact?.applicant_ids?.length
                ? _t("Create an applicant")
                : viewApplicantTitle,
            icon: "work",
            iconClass: "oi-filled",
            predicate: () =>
                this.voip.softphone.shouldShowApplicantButton && isApplicantButtonVisible,
            onClick: () => {
                const action = {
                    type: "ir.actions.act_window",
                    name: _t("Applicants"),
                    res_model: "hr.applicant",
                    target: this.ui.isSmall ? "new" : "current",
                    context: {},
                };
                if (this.contact?.applicant_ids?.length > 1) {
                    action.domain = [["partner_id", "=", this.contact.id]];
                    action.views = [[false, "list"]];
                } else if (this.contact?.applicant_ids?.length === 1) {
                    action.res_id = this.contact.applicant_ids[0].id;
                    action.views = [[false, "form"]];
                } else {
                    action.views = [[false, "form"]];
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
