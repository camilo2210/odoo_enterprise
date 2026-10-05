import { onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

import {
    worksheetPropertiesField,
    WorksheetPropertiesFields,
} from "@worksheet/components/worksheet_properties/worksheet_properties_field";

export class FieldServiceWorksheetPropertiesFields extends WorksheetPropertiesFields {
    setup() {
        super.setup();
        onWillStart(async () => {
            this.isPlanningManager = await user.hasGroup("planning.group_planning_manager");
        });
    }

    get displayAddWorksheetPropertyButton() {
        return super.displayAddWorksheetPropertyButton && this.isPlanningManager;
    }

    _getClosestField() {
        return this.propertiesRef().closest(".o_field_field_service_worksheet_properties");
    }
}

export const fieldServiceWorksheetPropertiesField = {
    ...worksheetPropertiesField,
    component: FieldServiceWorksheetPropertiesFields,
};

registry
    .category("fields")
    .add("field_service_worksheet_properties", fieldServiceWorksheetPropertiesField);
