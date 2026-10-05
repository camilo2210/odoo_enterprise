import { t } from "@odoo/owl";
import { AiPrompt } from "@ai/ai_prompt/ai_prompt";
import { patch } from "@web/core/utils/patch";
import { PropertiesField } from "@web/views/fields/properties/properties_field";
import {
    PropertyDefinition,
    propertyDefinitionProps,
} from "@web/views/fields/properties/property_definition";

propertyDefinitionProps.propertiesModel = t.string();

patch(PropertiesField.prototype, {
    get additionalPropertyDefinitionProps() {
        return {
            ...super.additionalPropertyDefinitionProps,
            propertiesModel: this.props.record.resModel,
        };
    },
    async onAiClick(propertyName) {
        const value = await this.props.record.computeAiProperty(
            `${this.props.name}.${propertyName}`
        );
        this.onPropertyValueChange(propertyName, value);
    },

    async onPropertyDefinitionChange(propertyDefinition) {
        const propertyIndex = this._getPropertyIndex(propertyDefinition.name);
        const oldDefinition = this.propertiesList[propertyIndex];

        if (!oldDefinition.ai && propertyDefinition.ai) {
            const lastRecord = await this.orm.call(
                this.props.record._config.resModel,
                "search",
                [],
                { domain: [], limit: 1, order: "id DESC" }
            );
            const resId = lastRecord[0] || 0;
            if (this.props.record._config.resId) {
                propertyDefinition.ai_domain = [
                    "|",
                    ["id", ">=", resId - 50],
                    ["id", "=", this.props.record._config.resId],
                ];
            } else {
                propertyDefinition.ai_domain = [["id", ">=", resId - 50]];
            }
        }

        return await super.onPropertyDefinitionChange(...arguments);
    },
});

PropertyDefinition.components = { ...PropertyDefinition.components, AiPrompt };
