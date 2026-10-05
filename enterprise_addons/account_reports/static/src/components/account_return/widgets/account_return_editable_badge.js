import { registry } from "@web/core/registry";
import { Component, onMounted, signal, t, useProps } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class AccountReturnEditable extends Component {
    static template = "account_reports.AccountReturnEditableBadgeField";
    props = useProps({
        ...standardFieldProps,
        type: t.string(),
        placeholder: t.string().optional(),
        widget_class: t.string().optional(),
    });

    textareaRef = signal.ref();

    setup() {
        super.setup();
        onMounted(() => {
            if (this.textareaRef()) {
                this.resize();
            }
        });
    }

    updateField(event) {
        const value = event.target.value;
        this.props.record.update({ [this.props.name]: value });
        this.props.record.save();
    }

    resize() {
        // This can be replaced in the future by `field-sizing: content;` on the textarea
        // but it's not yet supported in all browsers (firefox and safari).
        this.textareaRef().style.height = "0"; // To force recalculation of scrollHeight
        this.textareaRef().style.height = this.textareaRef().scrollHeight + "px";
    }
}

export const accountReturnEditableBadge = {
    supportedTypes: ["char", "text"],
    component: AccountReturnEditable,
    extractProps: ({ placeholder, type, attrs }, dynamicInfo) => ({
        placeholder,
        type,
        widget_class: attrs.widget_class,
        readonly: dynamicInfo.readonly,
    }),
};

registry.category("fields").add("account_return_editable_badge", accountReturnEditableBadge);
