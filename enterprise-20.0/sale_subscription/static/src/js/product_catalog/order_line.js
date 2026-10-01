import { t, useProps } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ProductCatalogOrderLine } from "@product/product_catalog/order_line/order_line";

patch(ProductCatalogOrderLine.prototype, {
    setup() {
        super.setup();
        this.saleSubscriptionProps = useProps({
            plan_name: t.string().optional(),
        });
    },
});
