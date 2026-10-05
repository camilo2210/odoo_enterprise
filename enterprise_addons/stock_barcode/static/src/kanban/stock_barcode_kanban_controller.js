import { KanbanController } from "@web/views/kanban/kanban_controller";
import { user } from "@web/core/user";
import { useBus, useService } from "@web/core/utils/hooks";
import { useSubEnv } from "@web/owl2/utils";
import { markup, onWillStart } from "@odoo/owl";

export class StockBarcodeKanbanController extends KanbanController {
    setup() {
        super.setup(...arguments);
        useSubEnv({
            config: {
                ...this.env.config,
                disableSearchBarAutofocus: true,
            },
        });
        this.barcodeService = useService("barcode");
        useBus(this.barcodeService.bus, "barcode_scanned", (ev) =>
            this._onBarcodeScannedHandler(ev.detail.barcode)
        );
        onWillStart(async () => {
            this.batchEnabled = await user.hasGroup("stock.group_stock_picking_batch");
        });
    }

    openRecord(record) {
        if (!this.batchEnabled && record.data.batch_id) {
            // If the picking is batched and the batch setting is disabled, open the batch instead.
            return this.actionService.doAction(
                "stock_barcode.stock_barcode_picking_batch_client_action",
                { additionalContext: { active_id: record.data.batch_id.id } }
            );
        }
        this.actionService.doAction("stock_barcode.stock_barcode_picking_client_action", {
            additionalContext: { active_id: record.resId },
        });
    }

    async createRecord() {
        const resModel = this.props.resModel;
        const method =
            this.props.resModel === "stock.picking.batch"
                ? "open_new_batch_picking"
                : "action_open_new_picking";
        const action = await this.model.orm.call(resModel, method, [], {
            context: this.props.context,
        });
        if (action) {
            return this.actionService.doAction(action);
        }
        return super.createRecord(...arguments);
    }

    // --------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Called when the user scans a barcode.
     *
     * @param {String} barcode
     */
    async _onBarcodeScannedHandler(barcode) {
        const kwargs = { barcode, context: this.props.context };
        const res = await this.model.orm.call(this.props.resModel, "filter_on_barcode", [], kwargs);
        const action = res.action;
        if (action?.help) {
            action.help = markup(action.help);
            this.actionService.doAction(action);
        } else if (res.warning) {
            this.addNotification(res.warning, barcode);
        }
    }

    addNotification(content, _barcode) {
        const params = { title: content.title, type: "danger" };
        this.model.notification.add(content.message, params);
    }
}
