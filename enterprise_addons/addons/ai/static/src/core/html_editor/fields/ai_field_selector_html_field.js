import { HtmlField, htmlField, htmlFieldProps } from "@html_editor/fields/html_field";
import { AIFieldSelectorPlugin } from "@ai/ai_prompt/ai_field_selector_plugin";
import { registry } from "@web/core/registry";

import { useProps, t } from "@odoo/owl";

export class AIFieldSelectorHtmlField extends HtmlField {
    props = useProps({
        ...htmlFieldProps,
        // The name of the field that references the model whose fields will be shown to the user when using /field
        aiFieldSelectorModelReferenceField: t.string(),
    });

    getConfig() {
        const config = super.getConfig();
        config["Plugins"] = [...config["Plugins"], AIFieldSelectorPlugin];
        config["fieldSelectorResModel"] =
            this.props.record.data[this.props.aiFieldSelectorModelReferenceField];
        return config;
    }
}

export const aiFieldSelectorHtmlField = {
    ...htmlField,
    component: AIFieldSelectorHtmlField,
    extractProps({ attrs, options }, dynamicInfo) {
        const props = htmlField.extractProps({ attrs, options }, dynamicInfo);
        const aiFieldSelectorModelReferenceField = options.aiFieldSelectorModelReferenceField;
        return { ...props, aiFieldSelectorModelReferenceField };
    },
};
registry.category("fields").add("ai_field_selector_html_field", aiFieldSelectorHtmlField);
