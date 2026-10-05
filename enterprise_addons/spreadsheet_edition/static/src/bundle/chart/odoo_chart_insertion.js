import { helpers, stores } from "@odoo/o-spreadsheet";
import { initCallbackRegistry } from "@spreadsheet/o_spreadsheet/init_callbacks";
import { Domain } from "@web/core/domain";
const { UuidGenerator } = helpers;

const { SidePanelStore } = stores;

export function insertChart(chartData) {
    const chartType = `${chartData.metaData.mode}`;
    const definition = {
        dataSource: {
            type: "odoo",
            metaData: {
                // Transform the fields object into their string representation (with the fields object' toJSON())
                groupBy: JSON.parse(JSON.stringify(chartData.metaData.groupBy)),
                measure: chartData.metaData.measure,
                order: chartData.metaData.order,
                resModel: chartData.metaData.resModel,
            },
            searchParams: {
                ...chartData.searchParams,
                domain: new Domain(chartData.searchParams.domain).toJson(),
            },
            actionXmlId: chartData.actionXmlId,
            cumulatedStart: chartData.metaData.cumulatedStart,
        },
        humanize: true,
        stacked: chartData.metaData.stacked,
        axisType: chartData.metaData.axisType,
        fillArea: chartType === "line",
        cumulative: chartData.metaData.cumulated || undefined,
        title: { text: chartData.name },
        background: "#FFFFFF",
        legendPosition: "top",
        verticalAxisPosition: "left",
        type: chartType,
        dataSourceId: UuidGenerator.smallUuid(),
        id: UuidGenerator.smallUuid(),
        dataSetStyles: {},
    };
    if (chartType === "bar" && chartData.metaData.stacked) {
        definition.showTotalLine = true;
    }
    return (model, stores) => {
        model.dispatch("CREATE_CHART", {
            sheetId: model.getters.getActiveSheetId(),
            figureId: UuidGenerator.smallUuid(),
            chartId: definition.id,
            col: 0,
            row: 0,
            offset: { x: 10, y: 10 },
            definition,
        });
        model.dispatch("UPDATE_ODOO_LINK_TO_CHART", {
            chartId: definition.id,
            odooLink: {
                type: "dataSource",
                dataSourceCoreId: definition.id,
                dataSourceType: "chart",
            },
        });
        const sidePanel = stores.get(SidePanelStore);
        sidePanel.open("ChartPanel", { chartId: definition.id });
    };
}

initCallbackRegistry.add("insertChart", insertChart);
