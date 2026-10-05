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
        id: 4,
        name: "SIX",
        type: "bank",
        image: false,
        sequence: 1,
        payment_method_type: "terminal",
        payment_provider: "six_iot",
        default_qr: false,
        iot_device_id: 6,
        write_date: "2025-01-01 10:00:00",
    },
];
