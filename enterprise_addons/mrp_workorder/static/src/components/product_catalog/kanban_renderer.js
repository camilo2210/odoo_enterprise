import { ProductCatalogKanbanRenderer } from "@product/product_catalog/kanban_renderer";
import { patch } from "@web/core/utils/patch";
import { useProps, t } from "@odoo/owl";

patch(ProductCatalogKanbanRenderer.prototype, {
    setup() {
        super.setup();
        this.productCatalogProps = useProps({
            pushCatalogKanbanUpdate: t.function().optional(),
        });
    },
});
