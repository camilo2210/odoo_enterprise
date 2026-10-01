import { useProps, t } from "@odoo/owl";
import { binaryField, BinaryField, binaryFieldProps } from "@web/views/fields/binary/binary_field";
import { registry } from "@web/core/registry";


export class PayRunBinaryField extends BinaryField {
    static template = "hr_payroll.PayRunBinaryField";
    props = useProps({
        ...binaryFieldProps,
        formatField: t.string().optional(),
    });

    get format() {
        return this.props.record.data[this.props.formatField] || "";
    }
}

export const payRunBinaryField = {
    ...binaryField,
    component: PayRunBinaryField,
    extractProps: ({ attrs, options }) => {
        return {
            ...binaryField.extractProps({ attrs, options }),
            formatField: attrs.format,
        };
    }
};

registry.category("fields").add("payrun_binary", payRunBinaryField);
