import { patch } from "@web/core/utils/patch";
import { PosPrinter } from "@point_of_sale/../tests/unit/data/pos_printer.data";

patch(PosPrinter.prototype, {
    _load_pos_data_fields() {
        return [...super._load_pos_data_fields(), "iot_device_id"];
    },
});

PosPrinter._records = [
    ...PosPrinter._records,
    {
        id: 2,
        name: "IoT Receipt Printer",
        iot_device_id: 2,
        printer_type: "iot",
        use_type: "receipt",
        write_date: "2025-01-01 10:00:00",
    },
];
