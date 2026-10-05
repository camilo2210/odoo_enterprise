import { components, constants, helpers } from "@odoo/o-spreadsheet";
import { Component, proxy, t, useProps } from "@odoo/owl";
import { ModelSelector } from "@web/core/model_selector/model_selector";
import { useService } from "@web/core/utils/hooks";
import { PivotArchParser } from "@web/views/pivot/pivot_arch_parser";
import { addEmptyGranularity } from "@spreadsheet/pivot/pivot_helpers";
import { OdooPivot } from "@spreadsheet/pivot/odoo_pivot";
import { range } from "@web/core/utils/numbers";

const { PIVOT_INSERT_TABLE_STYLE_ID } = constants;
const { Section } = components;
const { UuidGenerator } = helpers;

export class NewPivotSidePanel extends Component {
    static template = "spreadsheet_edition.NewPivotSidePanel";
    static components = {
        Section,
        ModelSelector,
    };

    props = useProps({
        onCloseSidePanel: t.function(),
    });

    setup() {
        this.state = proxy({
            model: undefined,
        });
        this.viewService = useService("view");
    }

    get isSaveAllowed() {
        return this.state.model;
    }

    onModelSelected(model) {
        this.state.model = model;
    }

    async _getPivot() {
        const { fields, views } = await this.viewService.loadViews({
            resModel: this.state.model.technical,
            views: [[false, "pivot"]],
        });
        const archInfo = new PivotArchParser().parse(views.pivot.arch);

        // This step extracts measures, rows, and columns from the archInfo of pivot structure
        const activeMeasures = archInfo.activeMeasures.length
            ? archInfo.activeMeasures
            : ["__count"];
        const measures = activeMeasures.map((measure) => ({
            id: `${measure}:${fields[measure]?.aggregator || "count"}`,
            fieldName: measure,
            aggregator: fields[measure]?.aggregator || "count",
        }));

        return {
            type: "ODOO",
            name: this.state.model.label,
            model: this.state.model.technical,
            rows: addEmptyGranularity(archInfo.rowGroupBys, fields),
            columns: addEmptyGranularity(archInfo.colGroupBys, fields),
            measures,
            style: { tableStyleId: PIVOT_INSERT_TABLE_STYLE_ID },
        };
    }

    async save() {
        const pivotId = UuidGenerator.smallUuid();
        const pivot = await this._getPivot();
        const result = this.env.model.dispatch("ADD_PIVOT", {
            pivotId,
            pivot,
        });
        if (!result.isSuccessful) {
            throw new Error(`Couldn't insert pivot in spreadsheet. Reasons : ${result.reasons}`);
        }

        const ds = this.env.model.getters.getPivot(pivotId);
        if (!(ds instanceof OdooPivot)) {
            throw new Error("The pivot data source is not an OdooPivot");
        }
        await ds.load();
        const table = ds.getCollapsedTableStructure();

        this.env.model.dispatch("INSERT_NEW_ODOO_PIVOT", {
            pivotId,
            pivotName: pivot.name,
            tableExport: table.export(),
            insertInNewSheet: true,
            mode: "dynamic",
        });
        const cols = range(0, table.columns.length);
        this.env.model.dispatch("AUTORESIZE_COLUMNS", {
            sheetId: this.env.model.getters.getActiveSheetId(),
            cols,
        });
        this.env.openSidePanel("PivotSidePanel", { pivotId });
    }
}
