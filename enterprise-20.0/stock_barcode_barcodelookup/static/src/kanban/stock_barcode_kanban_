import { patch } from "@web/core/utils/patch";

import { StockBarcodeKanbanController } from "@stock_barcode/kanban/stock_barcode_kanban_controller";

patch(StockBarcodeKanbanController.prototype, {
    /**
     * We need to allow product creation from the scanner in
     * main/operations screens
     *
     * @override
     */
    async addNotification(content, barcode) {
        if (content.product_found) {
            return super.addNotification(...arguments);
        }
        const barcodeData = { barcode, content: content.message };
        this.barcodeService.bus.trigger("create_product", { barcodeData });
    },
});
