import { useProps, types, usePlugin } from "@odoo/owl";
import { components, helpers } from "@odoo/o-spreadsheet";
import { ODOO_AGGREGATORS, getRelationalFieldDefinition } from "@spreadsheet/pivot/pivot_helpers";
import { useService } from "@web/core/utils/hooks";
import { SidepanelModelFieldSelector } from "../../../components/sidepanel_model_field_selector/sidepanel_model_field_selector";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

const { PivotLayoutConfigurator } = components;
const { isDateOrDatetimeField } = helpers;

export class OdooPivotLayoutConfigurator extends PivotLayoutConfigurator {
    static template = "spreadsheet_edition.OdooPivotLayoutConfigurator";
    static components = {
        ...PivotLayoutConfigurator.components,
        SidepanelModelFieldSelector,
    };

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        super.setup(...arguments);
        this.odooProps = useProps({
            addDraftField: types.function(),
        });
        this.fieldService = useService("field");
        this.AGGREGATORS = ODOO_AGGREGATORS;
    }

    async addColumnDimension(fieldName) {
        const definition = await getRelationalFieldDefinition(
            this.props.definition.model,
            fieldName,
            this.fieldService
        );
        this.odooProps.addDraftField(fieldName, definition);
        super.addColumnDimension(fieldName);
    }

    async addRowDimension(fieldName) {
        const definition = await getRelationalFieldDefinition(
            this.props.definition.model,
            fieldName,
            this.fieldService
        );
        this.odooProps.addDraftField(fieldName, definition);
        super.addRowDimension(fieldName);
    }

    get allDimensions() {
        return this.props.definition.rows.concat(this.props.definition.columns);
    }

    filterField(field, path) {
        const RELATIONAL_FIELDS = new Set(["many2one", "one2many"]);
        if (!field.groupable) {
            return false;
        }
        const fullField = path ? `${path}.${field.name}` : field.name;
        const isFieldAlreadyPresent = isDateOrDatetimeField(field)
            ? this.props.unusedGranularities[fullField]?.size === 0
            : this.allDimensions.some((f) => f.fieldName === fullField);
        if (RELATIONAL_FIELDS.has(field.type)) {
            return { isFieldAlreadyPresent };
        }
        if (!isFieldAlreadyPresent) {
            return true;
        }
        return false;
    }
}
