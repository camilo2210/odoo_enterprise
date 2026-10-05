import { t, useProps } from "@odoo/owl";
import { ProductCatalogSaleOrderLine } from "@sale_stock/product_catalog/sale_order_line/sale_order_line";
import { patch } from "@web/core/utils/patch";

patch(ProductCatalogSaleOrderLine, {
    template: "planning_field_service_sale_stock.ProductCatalogSaleOrderLine",
});
patch(ProductCatalogSaleOrderLine.prototype, {
    setup() {
        super.setup();
        this.fsmProps = useProps({
            tracking: t.boolean().optional(),
            minimumQuantityOnProduct: t.number().optional(),
        });
    },

    get disableRemove() {
        if (this.env.intervention_id) {
            return this.props.quantity === this.fsmProps.minimumQuantityOnProduct;
        }
        return this.props.quantity === this.deliveryProps.deliveredQty;
    },
});
