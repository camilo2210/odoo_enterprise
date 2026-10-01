import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { BarcodeView } from "@barcodes/components/barcode_view";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { markup, onWillStart } from "@odoo/owl";
import { StockBarcodeMainScanner } from "../main_scanner/main_scanner";

export class StockBarcodeKanbanRenderer extends KanbanRenderer {
    static template = "stock_barcode.KanbanRenderer";
    static components = {
        ...super.components,
        BarcodeView,
        StockBarcodeMainScanner,
    };

    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.barcodeService = useService("barcode");
        this.orm = useService("orm");
        this.activeId = this.props.list.evalContext.active_id;
        this.resModel = this.props.list.model.config.resModel;
        this.displayTransferProtip =
            this.activeId && ["stock.picking", "stock.picking.batch"].includes(this.resModel);
        onWillStart(this.onWillStart);
    }

    _onScannerResult(barcode) {
        this.barcodeService.bus.trigger("barcode_scanned", { barcode });
    }

    _onScannerError(error) {
        console.error(error);
    }

    async onWillStart() {
        const groups = [
            "stock.group_tracking_lot",
            "stock.group_production_lot",
            "stock.group_stock_picking_batch",
            "uom.group_uom",
        ];
        const hasGroups = await Promise.all(groups.map((g) => user.hasGroup(g)));
        this.packageEnabled = hasGroups[0];
        this.trackingEnabled = hasGroups[1];
        this.batchEnabled = hasGroups[2];
        this.uomEnabled = hasGroups[3];
        if (
            this.activeId &&
            ["stock.picking", "stock.picking.batch"].includes(this.resModel) &&
            this.batchEnabled
        ) {
            const modelToSearch =
                this.resModel === "stock.picking" ? "stock.picking.batch" : "stock.picking";
            this.otherRecordsCount = await this.orm.call(
                "stock.picking.type",
                "get_model_records_count",
                [this.activeId, modelToSearch]
            );
        }
    }

    async displayPickings() {
        if (this.resModel === "stock.picking") {
            return;
        }
        const action = await this.orm.call(
            "stock.picking.type",
            "get_action_picking_tree_ready_kanban",
            [this.activeId]
        );
        // markup: help is coming from HTML field on ir.actions.actions
        action.help = markup(action.help);
        return this.displayAction(action);
    }

    async displayBatches() {
        if (this.resModel === "stock.picking.batch") {
            return;
        }
        const action = await this.orm.call(
            "stock.picking.type",
            "action_picking_batch_barcode_kanban",
            [this.activeId]
        );
        // markup: help is coming from HTML field on ir.actions.actions
        action.help = markup(action.help);
        return this.displayAction(action);
    }

    displayAction(action) {
        return this.actionService.doAction(action, {
            stackPosition: "replaceCurrentAction",
            additionalContext: this.props.list.evalContext,
        });
    }

    get transferTip() {
        const tags = { bold_s: markup`<b>`, bold_e: markup`</b>` };

        if (this.trackingEnabled) {
            if (this.packageEnabled) {
                if (this.uomEnabled) {
                    return _t(
                        "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, a %(bold_s)s lot%(bold_e)s, a %(bold_s)s packaging%(bold_e)s, or a %(bold_s)s package%(bold_e)s to filter your records",
                        tags
                    );
                }
                return _t(
                    "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, a %(bold_s)s lot%(bold_e)s, or a %(bold_s)s package%(bold_e)s to filter your records",
                    tags
                );
            } else if (this.uomEnabled) {
                return _t(
                    "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, a %(bold_s)s lot%(bold_e)s, or a %(bold_s)s packaging%(bold_e)s to filter your records",
                    tags
                );
            }
            return _t(
                "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, or a %(bold_s)s lot%(bold_e)s to filter your records",
                tags
            );
        } else if (this.packageEnabled) {
            if (this.uomEnabled) {
                return _t(
                    "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, a %(bold_s)s packaging%(bold_e)s, or a %(bold_s)s package%(bold_e)s to filter your records",
                    tags
                );
            }
            return _t(
                "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, or a %(bold_s)s package%(bold_e)s to filter your records",
                tags
            );
        } else if (this.uomEnabled) {
            return _t(
                "Scan a %(bold_s)s transfer%(bold_e)s, a %(bold_s)s product%(bold_e)s, or a %(bold_s)s packaging%(bold_e)s to filter your records",
                tags
            );
        }
        return _t(
            "Scan a %(bold_s)s transfer%(bold_e)s or a %(bold_s)s product%(bold_e)s to filter your records",
            tags
        );
    }
}

registry.category("views").add("stock_barcode_kanban", {
    ...kanbanView,
    Renderer: StockBarcodeKanbanRenderer,
});
