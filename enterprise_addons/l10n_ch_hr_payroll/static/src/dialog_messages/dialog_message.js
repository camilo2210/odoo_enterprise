/** @odoo-module **/
import { t, useProps } from "@odoo/owl";
import { X2ManyField, x2ManyField, x2ManyFieldProps } from "@web/views/fields/x2many/x2many_field";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { CharField } from "@web/views/fields/char/char_field";
import { FloatField } from "@web/views/fields/float/float_field";
import { IntegerField } from "@web/views/fields/integer/integer_field";
import { BooleanField } from "@web/views/fields/boolean/boolean_field";
import { DateTimeField } from '@web/views/fields/datetime/datetime_field';
import { RadioField } from "@web/views/fields/radio/radio_field";
import { swissdecFormat } from "@l10n_ch_hr_payroll/components/swissdec_format";

/** Classes of the widget of each answer type, as set by the Field component in form views. */
const ANSWER_FIELD_CLASSES = {
    String: "o_field_char",
    Integer: "o_field_integer",
    Double: "o_field_float",
    Boolean: "o_field_boolean",
    Date: "o_field_date",
    DateTime: "o_field_datetime",
    Amount: "o_field_float d-inline-flex align-items-baseline gap-2",
    YesNoUnknown: "o_field_radio",
};

export class DialogMessagesRenderer extends X2ManyField {
    static template = "l10n_ch_hr_payroll.DialogMessagesRenderer";
    props = useProps({
        ...x2ManyFieldProps,
        context: t.object().optional(),
    });
    static components = {
        CharField,
        RadioField,
        DateTimeField,
        FloatField,
        IntegerField,
        BooleanField,
    };

    /** Paragraphs of the dialog, grouped under their section heading. */
    get dialogSections() {
        const sections = [{ heading: false, paragraphs: [] }];
        for (const dialogField of this.props.record.data[this.props.name].records) {
            if (dialogField.data.field_type === "section") {
                sections.push({ heading: dialogField, paragraphs: [] });
            } else {
                sections.at(-1).paragraphs.push(dialogField);
            }
        }
        return sections.filter((section) => section.heading || section.paragraphs.length);
    }

    getAnswerClass(data) {
        return [
            "o_field_widget mb-0",
            ANSWER_FIELD_CLASSES[data.swissdec_answer_value_type] || "",
            ["Boolean", "Amount"].includes(data.swissdec_answer_value_type) ? "" : "w-100",
            data.swissdec_answer_optional ? "" : "o_required_modifier",
        ].join(" ");
    }

    formatValue(data) {
        switch (data.swissdec_value_type) {
            case "Amount":
            case "Double":
                return swissdecFormat.amount(data.swissdec_value);
            case "Date":
                return swissdecFormat.date(data.swissdec_value);
            case "DateTime":
                return swissdecFormat.dateTime(data.swissdec_value);
            default:
                return data.swissdec_value;
        }
    }
}

export const dialogMessageField = {
    ...x2ManyField,
    component: DialogMessagesRenderer,
    displayName: _t("Dialog Message"),
};


registry.category("fields").add("dialog_message", dialogMessageField);
