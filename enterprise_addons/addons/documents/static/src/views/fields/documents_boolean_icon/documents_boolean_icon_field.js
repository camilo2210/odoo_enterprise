import { useProps, t } from "@odoo/owl";
import { registry } from "@web/core/registry";
import {
    booleanIconField,
    BooleanIconField,
} from "@web/views/fields/boolean_icon/boolean_icon_field";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class DocumentsBooleanIconField extends BooleanIconField {
    static template = "documents.DocumentsBooleanIconField";
    // Inline copy of BooleanIconField's schema (no exported const in web)
    props = useProps({
        ...standardFieldProps,
        icon: t.string().optional("check_box"),
        iconClass: t.string().optional(),
        label: t.string().optional(),
        btnTrueClass: t.string().optional(),
        btnFalseClass: t.string().optional(),
    });
}

export const documentsBooleanIconField = {
    ...booleanIconField,
    component: DocumentsBooleanIconField,
    extractProps: (...args) => {
        const [{ options }] = args;
        return {
            ...booleanIconField.extractProps(...args),
            btnTrueClass: options.btn_true_class,
            btnFalseClass: options.btn_false_class,
        };
    },
};

registry.category("fields").add("documents_boolean_icon", documentsBooleanIconField);
