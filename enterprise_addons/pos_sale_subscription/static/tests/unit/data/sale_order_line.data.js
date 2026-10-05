import { SaleOrderLine } from "@pos_sale/../tests/unit/data/sale_order_line.data";

SaleOrderLine._records = [
    ...SaleOrderLine._records,
    {
        id: 5,
        display_name: "These recurring products are discounted",
        product_id: 6,
        product_uom_qty: 3,
        price_unit: 50,
        price_total: 150,
        discount: 0,
        qty_delivered: 0,
        qty_invoiced: 0,
        qty_to_invoice: 3,
        display_type: "subscription_discount",
        name: "These recurring products are discounted",
        tax_ids: [],
        is_downpayment: false,
        extra_tax_data: {},
        write_date: "2025-07-03 17:04:14",
    },
];
