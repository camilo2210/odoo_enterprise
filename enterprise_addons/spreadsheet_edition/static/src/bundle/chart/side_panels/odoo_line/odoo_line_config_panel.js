import { components } from "@odoo/o-spreadsheet";
import { patch } from "@web/core/utils/patch";

const { LineConfigPanel } = components;

patch(LineConfigPanel.prototype, {
    onUpdateCumulatedStart(cumulatedStart) {
        this.props.updateChart(this.props.chartId, {
            dataSource: {
                ...this.props.definition.dataSource,
                cumulatedStart,
            },
        });
    },
});
