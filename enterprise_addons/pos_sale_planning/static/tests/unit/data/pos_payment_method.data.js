import { patch } from "@web/core/utils/patch";
import { PosPaymentMethod } from "@point_of_sale/../tests/unit/data/pos_payment_method.data";

patch(PosPaymentMethod.prototype, {
    _load_pos_data_fields() {
        return [...super._load_pos_data_fields(), "resource_ids"];
    },
});

PosPaymentMethod._records = [
    ...PosPaymentMethod._records,
    {
        id: 4,
        name: "Resource PM",
        payment_provider: false,
        type: "resource",
        image: false,
        sequence: 3,
        payment_method_type: "none",
        default_qr: false,
        resource_ids: [10, 11],
    },
];
