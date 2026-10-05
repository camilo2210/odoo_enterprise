import { PosConfig } from "@point_of_sale/../tests/unit/data/pos_config.data";

PosConfig._records = PosConfig._records.map((record) => ({
    ...record,
    use_iot_box: true,
    iot_device_ids: [2, 3, 4, 5],
    iot_printer_id: 2,
    iot_display_id: 3,
    iot_scale_id: 5,
    iot_scanner_ids: [4],
    other_devices: true,
    receipt_printer_ids: [2],
    payment_method_ids: [...record.payment_method_ids, 5, 6],
}));
