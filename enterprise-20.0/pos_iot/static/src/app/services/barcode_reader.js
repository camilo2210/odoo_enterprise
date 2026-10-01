import { patch } from "@web/core/utils/patch";
import {
    BarcodeReader,
    barcodeReaderService,
} from "@point_of_sale/app/services/barcode_reader_service";

patch(barcodeReaderService, {
    dependencies: [...barcodeReaderService.dependencies, "iot_http"],
});

patch(BarcodeReader.prototype, {
    setup(parser, { iot_http }) {
        super.setup(...arguments);
        this.iotHttp = iot_http;
    },
    /**
     * @param {Object} iotBarcodeReaders
     */
    setupListeners(iotBarcodeReaders) {
        this.scanners = iotBarcodeReaders ??= {};
        for (const scanner of Object.values(this.scanners)) {
            this.keepListening(scanner);
        }
    },
    /**
     * @param {Object} scanner
     */
    keepListening(scanner) {
        this.iotHttp.onMessage(
            scanner.iot_id,
            scanner.identifier,
            (barcode) => {
                this.scan(barcode.value);
                this.keepListening(scanner);
            },
            () => this.keepListening(scanner)
        );
    },
});
