import { registry } from "@web/core/registry";
import { exprToBoolean } from "@web/core/utils/strings";
import { _t } from "@web/core/l10n/translation";
import { PropertiesField } from "@web/views/fields/properties/properties_field";

export class WorksheetPropertiesFields extends PropertiesField {
    static template = "worksheet.WorksheetProperties";

    /*
    * handle the case when the add property is used even though there are 0 existing ones
     */
    async onPropertyCreateEmpty() {
        const recordSaved = await this.props.record.save();
        if (this.props.readonly || this.state.isInEditMode || !recordSaved) {
            return;
        }
        let canChangeDefinition = this.state.canChangeDefinition;
        if (!canChangeDefinition) {
            canChangeDefinition = await this.checkDefinitionWriteAccess();
            if (!canChangeDefinition) {
                this.notification.add(this._getPropertyEditWarningText(), {
                    type: "warning",
                });
            }
        }
        const isInEditMode = canChangeDefinition && !this.props.readonly;
        this.state.canChangeDefinition = !!canChangeDefinition;
        this.setEditMode(isInEditMode);
        if (isInEditMode && this.propertiesList.length === 0) {
            const newName = this.generatePropertyName("char");
            const propertiesDefinitions = [{
                name: newName,
                string: _t("Property 1"),
                type: "char",
                definition_changed: true,
            }];
            this.initialValues[newName] = { name: newName, type: "char" };
            this.openPropertyDefinition = newName;
            await this.props.record.update({ [this.props.name]: propertiesDefinitions });
        }
    }

    get displayAddWorksheetPropertyButton() {
        return this.propertiesList.length == 0 && !this.state.isInEditMode
    }

    _getClosestField() {
        return this.propertiesRef().closest(".o_field_worksheet_properties");
    }
}

export const worksheetPropertiesField = {
    component: WorksheetPropertiesFields,
    displayName: _t("Worksheet Properties"),
    supportedTypes: ["properties"],
    additionalClasses: ["d-block"],
    extractProps({ attrs }, dynamicInfo) {
        return {
            context: dynamicInfo.context,
            columns: parseInt(attrs.columns || "1"),
            editMode: exprToBoolean(attrs.editMode),
        };
    },
};

registry.category("fields").add("worksheet_properties", worksheetPropertiesField);
