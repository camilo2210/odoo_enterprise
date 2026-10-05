import { _t } from "@web/core/l10n/translation";
import { GanttPopover } from "@web_gantt/gantt_popover";
import { GanttRenderer } from "@web_gantt/gantt_renderer";

class MRPProductionGanttPopover extends GanttPopover {
    get openRecordButtonLabel() {
        return _t("Open Manufacturing Orders");
    }
}

export class MRPProductionGanttRenderer extends GanttRenderer {
    static components = {
        ...GanttRenderer.components,
        Popover: MRPProductionGanttPopover,
    };
    static rowHeaderTemplate = "mrp_workorder.MRPProductionGanttRenderer.RowHeader";

    setup() {
        super.setup();
        this.preventClick = true;
    }

    getDisplayName(pill) {
        const { record } = pill;
        return `${record.display_name} - ${record.product_qty} ${record.uom_id.display_name}`;
    }

    async displayListView(productId) {
        this.actionService.doAction("mrp_workorder.mrp_production_products_gantt", {
            additionalContext: {
                search_default_product_id: productId,
            },
            onClose: async () => {
                await this.model.fetchData();
            },
        });
    }

    onRowHeaderClicked(row) {
        if (row.groupedByField === "product_id") {
            this.displayListView(row.resId);
        }
    }
}
