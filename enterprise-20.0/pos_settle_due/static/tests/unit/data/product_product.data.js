import { ProductProduct } from "@point_of_sale/../tests/unit/data/product_product.data";

ProductProduct._records = [
    ...ProductProduct._records,
    {
        id: 205,
        product_tmpl_id: 205,
        barcode: false,
        price_extra: 0,
        active: true,
    },
    {
        id: 206,
        product_tmpl_id: 206,
        barcode: false,
        price_extra: 0,
        active: true,
    },
];
