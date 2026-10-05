import { ProductCatalogKanbanRecord } from "@product/product_catalog/kanban_record";
import { patch } from "@web/core/utils/patch";
import { useProps, t } from "@odoo/owl";

patch(ProductCatalogKanbanRecord.prototype, {
    setup() {
        super.setup();
        this.productCatalogProps = useProps({
            pushCatalogKanbanUpdate: t.function().optional(),
        });
    },

    _getUpdateQuantityAndGetPriceParams() {
        const params = {
            ...super._getUpdateQuantityAndGetPriceParams(),
            from_shop_floor: this.props.record.context.from_shop_floor,
        };
        if ("workorder_id" in this.props.record.context) {
            params.workorder_id = this.props.record.context.workorder_id;
        }
        return params;
    },

    _onQuantityChange() {
        const result = super._onQuantityChange();
        this.productCatalogProps.pushCatalogKanbanUpdate?.(result);
    },
});
