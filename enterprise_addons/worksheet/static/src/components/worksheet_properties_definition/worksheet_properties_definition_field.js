import { registry } from "@web/core/registry";
import { PROPERTIES_INFO } from "@web/views/fields/properties/property_definition";
import { PropertiesDefinitionField, propertiesDefinitionField } from "@web/views/fields/properties/properties_definition_field";

export class WorksheetPropertiesDefinitionField extends PropertiesDefinitionField {
    static template = "worksheet.WorksheetPropertiesDefinitionField";

    setup() {
        super.setup();
        this.state.isInEditMode = true;
    }

    typeLabel(type) {
        return PROPERTIES_INFO[type]?.label;
    }

}

export const worksheetPropertiesDefinitionField = {
    ...propertiesDefinitionField,
    component: WorksheetPropertiesDefinitionField,
    additionalClasses: ["o_field_properties_definition"],
}

registry.category("fields").add("worksheet_properties_definition", worksheetPropertiesDefinitionField);
