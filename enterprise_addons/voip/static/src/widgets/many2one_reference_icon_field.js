import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { extractM2OFieldProps } from "@web/views/fields/many2one/many2one_field";
import { Many2OneReferenceField } from "@web/views/fields/many2one_reference/many2one_reference_field";

export const ICON_BY_MODEL_NAME = {
    "crm.lead": "star",
    "sale.order": "attach_money",
    "account.move": "receipt_long",
    subscription: "autorenew",
    "event.event": "local_bar",
    "event.registration": "confirmation_number",
    "helpdesk.ticket": "support",
    "project.task": "check",
    "purchase.order": "credit_card",
    "document.document": "article",
    "hr.employee": "badge",
    "stock.picking": "local_shipping",
    "res.partner": "person",
    "res.users": "person",
    "mrp.production": "build",
    "hr.applicant": "work",
    "fleet.vehicle": "directions_car",
    "survey.user_input": "how_to_vote",
    "calendar.event": "calendar_today",
};

export const FILLED_ICON_MODELS = [
    "crm.lead",
    "event.event",
    "res.partner",
    "hr.applicant",
    "event.registration",
    "survey.user_input",
    "calendar.event",
];

export class Many2OneReferenceIconField extends Many2OneReferenceField {
    static template = "web.Many2OneReferenceIconField";

    /**
     * Gets the icon class based on the record type or relation model.
     * Returns a default "description" if the model has no specific icon defined.
     * * @returns {string} The FontAwesome class
     */
    get modelIcon() {
        if (this.props.record.data.is_related_activity_document_subscription) {
            return ICON_BY_MODEL_NAME["subscription"];
        }
        return ICON_BY_MODEL_NAME[this.relation] || "description";
    }

    get modelIconClass() {
        return FILLED_ICON_MODELS.includes(this.relation) ? "oi-filled" : "";
    }

    get modelDisplayName() {
        return this.props.record.data.activity_res_model_id?.display_name;
    }
}

registry.category("fields").add("many2one_reference_icon", {
    component: Many2OneReferenceIconField,
    displayName: _t("Many2OneReference with Icon"),
    extractProps(staticInfo, dynamicInfo) {
        return extractM2OFieldProps(staticInfo, dynamicInfo);
    },
    relatedFields: [{ name: "display_name", type: "char" }],
    fieldDependencies: [{ name: "activity_res_model_id", type: "many2one" }],
    supportedTypes: ["many2one_reference"],
});
