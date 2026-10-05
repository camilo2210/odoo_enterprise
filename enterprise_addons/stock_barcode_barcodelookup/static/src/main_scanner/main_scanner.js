import { patch } from "@web/core/utils/patch";

import { StockBarcodeMainScanner } from "@stock_barcode/main_scanner/main_scanner";

patch(StockBarcodeMainScanner.prototype, {
    /**
     * We need to allow product creation from the scanner in
     * main/operations screens
     *
     * @override
     */
    async addNotification(content, barcode) {
        const barcodeData = { barcode, content };
        this.barcodeService.bus.trigger("create_product", { barcodeData });
    },
});
