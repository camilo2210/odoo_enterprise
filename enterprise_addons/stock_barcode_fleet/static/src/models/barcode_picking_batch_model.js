import BarcodePickingBatchModel from "@stock_barcode/models/barcode_picking_batch_model";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(BarcodePickingBatchModel.prototype, {
    get printButtons() {
        const buttons = super.printButtons;
        if (this.record.picking_type_code === "outgoing") {
            buttons.push({
                name: _t("Print CMR"),
                class: "o_print_cmr_batch",
                method: "action_print_cmr_batch",
            });
        }
        return buttons;
    },
});
