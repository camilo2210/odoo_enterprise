import { SaleOrder } from "@pos_sale/../tests/unit/data/sale_order.data";

SaleOrder._records = [
    ...SaleOrder._records,
    {
        id: 3,
        name: "S00002",
        state: "sale",
        order_line: [1, 5],
        partner_id: 3,
        pricelist_id: 1,
        fiscal_position_id: 1,
        amount_total: 650,
        amount_untaxed: 500,
        amount_unpaid: 650,
        partner_shipping_id: 3,
        partner_invoice_id: 3,
        date_order: "2025-07-03 17:04:14",
        write_date: "2025-07-03 17:04:14",
    },
];
