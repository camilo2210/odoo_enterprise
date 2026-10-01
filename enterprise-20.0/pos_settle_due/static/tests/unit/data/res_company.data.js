import { patch } from "@web/core/utils/patch";
import { ResCompany } from "@point_of_sale/../tests/unit/data/res_company.data";

patch(ResCompany.prototype, {
    _load_pos_data_fields() {
        return [...super._load_pos_data_fields(), "account_use_credit_limit"];
    },
});

ResCompany._records = [
    ...ResCompany._records,
    {
        id: 253,
        currency_id: 1,
        email: false,
        website: false,
        vat: false,
        additional_identifiers: false,
        name: "My Company",
        phone: "",
        partner_id: 1,
        country_id: 233,
        state_id: false,
        tax_calculation_rounding_method: "round_per_line",
        point_of_sale_use_ticket_qr_code: true,
        point_of_sale_ticket_unique_code: false,
        point_of_sale_ticket_portal_url_display_mode: "qr_code_and_url",
        street: "",
        city: "",
        zip: "",
        account_fiscal_country_id: 233,
        account_use_credit_limit: true,
    },
];
