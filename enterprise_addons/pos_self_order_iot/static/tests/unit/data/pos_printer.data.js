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
        id: 5,
        name: "IoT Preparation Printer",
        iot_device_id: 2,
        printer_type: "iot",
        product_categories_ids: [1, 2],
    },
];
