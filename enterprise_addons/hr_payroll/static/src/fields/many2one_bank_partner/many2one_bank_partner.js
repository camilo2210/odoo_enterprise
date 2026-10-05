import { _t } from "@web/core/l10n/translation";
import { markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { extractData, Many2One } from "@web/views/fields/many2one/many2one";
import { buildM2OFieldDescription, Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

/**
 * These classes and widget `many2one_bank` are meant to be
 * used only with res.partner.bank
 */

export class Many2XAutocompleteBank extends Many2XAutocomplete {
    buildRecordSuggestion(request, record) {
        const recordSuggestion = super.buildRecordSuggestion(request, record);
        const icon = record.allow_out_payment ? "security" : "error";
        const colorClass = record.allow_out_payment ? "text-success" : "text-danger";
        const title = record.allow_out_payment ? _t("Trusted") : _t("Untrusted");
        recordSuggestion.label = markup`<i class="me-1 oi ${colorClass}" data-icon="${icon}" title="${title}"></i> ${record.holder_name} (${recordSuggestion.label})`;
        return recordSuggestion;
    }

    get searchSpecification() {
        return {
            ...super.searchSpecification,
            allow_out_payment: {},
            holder_name: {},
        };
    }
}

function extractDataBank(record) {
    return {
        ...extractData(record),
        allow_out_payment: record.allow_out_payment,
        holder_name: record.holder_name,
    };
}

export class Many2OneBankPartner extends Many2One {
    static template = "hr_payroll.Many2OneBank";
    static components = {
        ...Many2One.components,
        Many2XAutocomplete: Many2XAutocompleteBank,
    };

    get many2XAutocompleteProps() {
        return {
            ...super.many2XAutocompleteProps,
            value: this.props.value.partner_id?.display_name,
            update: (records) => {
                const bankRecordData = records && records[0] ? extractDataBank(records[0]) : false;
                this.update(bankRecordData);
            },
        };
    }
}

export class Many2OneBankPartnerField extends Many2OneField {
    static components = {
        ...Many2OneField.components,
        Many2One: Many2OneBankPartner,
    };

    get m2oProps() {
        const props = super.m2oProps;
        props.cssClass = `${props.cssClass ?? ''} d-flex`;
        return props;
    }
}

export const many2OneBankPartner = {
    ...buildM2OFieldDescription(Many2OneBankPartnerField),
    relatedFields: [
        { name: "allow_out_payment", type: "bool" },
        { name: "partner_id", type: "many2one", relation: "res.partner" },
    ],
};

registry.category("fields").add("many2one_bank_partner", many2OneBankPartner);
