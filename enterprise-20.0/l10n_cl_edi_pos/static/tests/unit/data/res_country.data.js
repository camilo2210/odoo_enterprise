import { ResCountry } from "@point_of_sale/../tests/unit/data/res_country.data";

ResCountry._records = [
    ...ResCountry._records,
    {
        id: 220,
        name: "Chile",
        code: "CL",
        vat_label: "RUT",
    },
];
