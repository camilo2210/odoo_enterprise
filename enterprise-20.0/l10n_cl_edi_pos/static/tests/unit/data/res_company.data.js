import { ResCompany } from "@point_of_sale/../tests/unit/data/res_company.data";

ResCompany._records = [
    ...ResCompany._records,
    {
        id: 257,
        currency_id: 141,
        email: false,
        website: false,
        vat: false,
        name: "My CL Company",
        phone: "",
        partner_id: 1,
        country_id: 220,
        state_id: false,
        tax_calculation_rounding_method: "round_per_line",
        point_of_sale_use_ticket_qr_code: true,
        point_of_sale_ticket_unique_code: false,
        point_of_sale_ticket_portal_url_display_mode: "qr_code_and_url",
        street: "",
        city: "",
        zip: "",
    },
];
