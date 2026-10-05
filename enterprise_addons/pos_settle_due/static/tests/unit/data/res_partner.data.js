import { patch } from "@web/core/utils/patch";
import { ResPartner } from "@point_of_sale/../tests/unit/data/res_partner.data";

patch(ResPartner.prototype, {
    _load_pos_data_fields() {
        return [
            ...super._load_pos_data_fields(),
            "credit_limit",
            "total_due",
            "use_partner_credit_limit",
            "invoices_amount_due",
            "commercial_partner_id",
        ];
    },
});

ResPartner._records = [
    ...ResPartner._records.map((record) => ({
        ...record,
        credit_limit: 0.0,
        use_partner_credit_limit: false,
    })),
    {
        id: 5,
        name: "User on budget",
        commercial_partner_id: 5,
        street: false,
        street2: false,
        city: false,
        state_id: false,
        country_id: false,
        vat: false,
        lang: "en_US",
        phone: false,
        zip: false,
        email: false,
        barcode: false,
        write_date: "2025-08-03 12:12:12",
        property_product_pricelist: false,
        parent_name: false,
        address: "\n\n  \n",
        invoice_emails: "",
        fiscal_position_id: false,
        credit_limit: 10,
        use_partner_credit_limit: true,
    },
];
