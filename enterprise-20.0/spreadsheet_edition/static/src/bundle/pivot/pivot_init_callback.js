//@ts-check

import { helpers, stores, constants } from "@odoo/o-spreadsheet";
import { OdooPivot } from "@spreadsheet/pivot/odoo_pivot";
import { addEmptyGranularity } from "@spreadsheet/pivot/pivot_helpers";
import { Domain } from "@web/core/domain";
import { deepCopy } from "@web/core/utils/objects";
import { range } from "@web/core/utils/numbers";

const { pivotTimeAdapter, UuidGenerator } = helpers;

const { SidePanelStore } = stores;
const { PIVOT_INSERT_TABLE_STYLE_ID } = constants;

export function insertPivot(pivotData) {
    const fields = pivotData.metaData.fields;
    const activeMeasures = pivotData.metaData.activeMeasures;
    const measures = activeMeasures.map((measure) => {
        const aggregator =
            fields[measure]?.type === "monetary" ? "sum_currency" : fields[measure]?.aggregator;
        return {
            id: aggregator ? `${measure}:${aggregator}` : measure,
            fieldName: measure,
            aggregator,
        };
    });
    /** @type {import("@spreadsheet").OdooPivotCoreDefinition} */
    const pivot = deepCopy({
        type: "ODOO",
        name: pivotData.name,
        model: pivotData.metaData.resModel,
        domain: new Domain(pivotData.searchParams.domain).toJson(),
        context: pivotData.searchParams.context,
        rows: addEmptyGranularity(pivotData.metaData.fullRowGroupBys, fields),
        columns: addEmptyGranularity(pivotData.metaData.fullColGroupBys, fields),
        measures,
        actionXmlId: pivotData.actionXmlId,
        style: { tableStyleId: PIVOT_INSERT_TABLE_STYLE_ID },
    });
    /**
     * @param {import("@spreadsheet").OdooSpreadsheetModel} model
     */
    return async (model, stores) => {
        const sortedColumn = getPivotSortedColumn(model, pivotData, pivot.measures);
        if (sortedColumn) {
            pivot.sortedColumn = sortedColumn;
        }

        const pivotId = UuidGenerator.smallUuid();
        const result = model.dispatch("ADD_PIVOT", {
            pivotId,
            pivot,
        });
        if (!result.isSuccessful) {
            throw new Error(`Couldn't insert pivot in spreadsheet. Reasons : ${result.reasons}`);
        }

        const ds = model.getters.getPivot(pivotId);
        if (!(ds instanceof OdooPivot)) {
            throw new Error("The pivot data source is not an OdooPivot");
        }
        await ds.load();
        const table = ds.getExpandedTableStructure();

        model.dispatch("INSERT_NEW_ODOO_PIVOT", {
            pivotId,
            pivotName: pivot.name,
            tableExport: table.export(),
            insertInNewSheet: !this.isEmptySpreadsheet,
            mode: "static",
        });
        const sheetId = model.getters.getActiveSheetId();
        const cols = range(0, table.columns.length);
        model.dispatch("AUTORESIZE_COLUMNS", { sheetId, cols });
        const sidePanel = stores.get(SidePanelStore);
        sidePanel.open("PivotSidePanel", { pivotId });
    };
}

function getPivotSortedColumn(model, pivotData, measures) {
    const sortedColumn = pivotData.metaData.sortedColumn;
    if (!sortedColumn) {
        return undefined;
    }

    const measure = measures.find((measure) => measure.fieldName === sortedColumn.measure);
    if (!measure) {
        return undefined;
    }

    const fields = pivotData.metaData.fields;
    const sortedValues = sortedColumn.groupId[1];
    const sortColDomain = [];
    let currentBranch = pivotData.colGroupTree;

    for (let i = 0; i < sortedValues.length; i++) {
        let value = sortedValues[i];
        currentBranch = currentBranch.directSubTrees.get(value);
        const field = pivotData.metaData.fullColGroupBys[i];
        if (!field) {
            return undefined;
        }

        const [fieldName, granularity] = field.split(":");
        const fieldType = fields[fieldName].type;
        if (fieldType === "date" || fieldType === "datetime") {
            const normalizer = pivotTimeAdapter(granularity).normalizeServerValue;
            const readGroupResult = {
                [field]: [currentBranch.root.values.at(-1), currentBranch.root.labels.at(-1)],
            };
            const locale = model.getters.getLocale();
            value = normalizer(field, fields[fieldName], readGroupResult, locale);
        }

        sortColDomain.push({ value, field, type: fieldType });
    }

    return {
        domain: sortColDomain,
        order: sortedColumn.order,
        measure: measure.id,
    };
}
