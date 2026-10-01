import { patch } from "@web/core/utils/patch";
import { PosPaymentMethod } from "@point_of_sale/../tests/unit/data/pos_payment_method.data";

patch(PosPaymentMethod.prototype, {
    _load_pos_data_fields() {
        return [...super._load_pos_data_fields(), "iot_device_id"];
    },
});

PosPaymentMethod._records = [
    ...PosPaymentMethod._records,
    {
        id: 5,
        name: "Test IoT Terminal",
        payment_provider: false,
        type: "bank",
        image: false,
        sequence: 3,
        payment_method_type: "terminal",
        default_qr: false,
        iot_device_id: 7,
    },
    {
        id: 6,
        name: "Test IoT Terminal (unconfigured)",
        payment_provider: false,
        type: "bank",
        image: false,
        sequence: 4,
        payment_method_type: "terminal",
        default_qr: false,
        iot_device_id: false,
    },
];
