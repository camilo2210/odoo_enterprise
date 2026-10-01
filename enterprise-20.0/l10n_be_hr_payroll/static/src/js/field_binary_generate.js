import { useProps, proxy, t } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { BinaryField, binaryField, binaryFieldProps } from "@web/views/fields/binary/binary_field";


export class BinaryGenerateField extends BinaryField {
    static template = "l10n_be_hr_payroll.BinaryGenerateField";
    props = useProps({
        ...binaryFieldProps,
        generateAction: t.string().optional(),
        generateLabel: t.string().optional(_t("Generate")),
    });

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = proxy({ isGenerating: false });
    }

    get hasFile() {
        return Boolean(this.props.record.data[this.props.name]);
    }

    get buttonLabel() {
        return this.state.isGenerating ? _t("Generating...") : (this.props.generateLabel || _t("Generate"));
    }

    async onGenerate(ev) {
        ev?.preventDefault();
        ev?.stopPropagation();
        if (this.state.isGenerating || !this.props.generateAction) {
            return;
        }
        const { record } = this.props;
        if (!record.resId || record.dirty) {
            const saved = await record.save();
            if (!saved) {
                return;
            }
        }
        this.state.isGenerating = true;
        try {
            await this.orm.call(record.resModel, this.props.generateAction, [[record.resId]]);
            await record.load();
        } catch (error) {
            this.notification.add(_t("There was a problem while generating your file."), {
                type: "danger",
            });
            throw error;
        } finally {
            this.state.isGenerating = false;
        }
    }
}

export const binaryGenerateField = {
    ...binaryField,
    component: BinaryGenerateField,
    supportedOptions: [
        ...binaryField.supportedOptions,
        {
            label: _t("Generate action"),
            name: "generate_action",
            type: "string",
        },
        {
            label: _t("Generate label"),
            name: "generate_label",
            type: "string",
        },
    ],
    extractProps: ({ attrs, options }) => ({
        ...binaryField.extractProps({ attrs, options }),
        generateAction: options.generate_action,
        generateLabel: options.generate_label,
    }),
};

registry.category("fields").add("binary_generate", binaryGenerateField);
registry.category("fields").add("list.binary_generate", binaryGenerateField);
