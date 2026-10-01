import { ResCurrency } from "@point_of_sale/../tests/unit/data/res_currency.data";

ResCurrency._records = [
    ...ResCurrency._records,
    {
        id: 141,
        name: "CLP",
        symbol: "$",
        position: "before",
        rounding: 1,
        rate: 1,
        decimal_places: 0,
        iso_numeric: 152,
    },
];
