import { patch } from "@web/core/utils/patch";
import * as spreadsheet from "@odoo/o-spreadsheet";

const { ChartTypePicker } = spreadsheet.components;

const GEO_RES_MODELS = ["res.country", "res.country.state"];

/**
 * This patch is necessary to ensure that the chart type cannot be changed
 * between odoo charts and spreadsheet charts.
 */

patch(ChartTypePicker.prototype, {
    getSupportedChartTypes() {
        const supportedTypes = super.getSupportedChartTypes();

        const definition = this.env.model.getters.getChartDefinition(this.props.chartId);
        const isOdoo = definition.dataSource?.type === "odoo";
        if (isOdoo && !this.isGeoChartTypeAvailable(this.props.chartId)) {
            supportedTypes.delete("geo");
        }

        return supportedTypes;
    },
    isGeoChartTypeAvailable(chartId) {
        const dataSource = this.env.model.getters.getChartDataSource(chartId);
        const definition = this.env.model.getters.getChartDefinition(chartId);
        const groupBy = definition.dataSource.metaData.groupBy;
        if (!groupBy || groupBy.length !== 1 || !dataSource.isValid()) {
            return false;
        }
        const field = dataSource.getField(groupBy[0]);
        return field && field.type === "many2one" && GEO_RES_MODELS.includes(field.relation);
    },
});
