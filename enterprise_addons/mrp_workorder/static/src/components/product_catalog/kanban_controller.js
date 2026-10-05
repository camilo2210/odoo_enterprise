import { onWillDestroy, useProps, t } from "@odoo/owl";
import { ProductCatalogKanbanController } from "@product/product_catalog/kanban_controller";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(ProductCatalogKanbanController.prototype, {
    setup() {
        super.setup();
        this.productCatalogProps = useProps({
            onCatalogUpdated: t.function().optional(),
        });
        this.catalogKanbanUpdates = [];
        // The `onCatalogUpdated` props provides a callback to be called
        // once all the catalogKanbanUpdates have been resolved
        if (this.productCatalogProps.onCatalogUpdated) {
            onWillDestroy(async () => {
                Promise.all(this.catalogKanbanUpdates).then(() => {
                    this.productCatalogProps.onCatalogUpdated();
                });
            });
        }
    },

    pushCatalogKanbanUpdate(update) {
        this.catalogKanbanUpdates.push(update);
    },

    _defineButtonContent() {
        if (this.props.context.from_shop_floor) {
            this.buttonString = _t("Back to ShopFloor");
        } else {
            super._defineButtonContent();
        }
    },

    async backToQuotation() {
        if (this.props.context.from_shop_floor) {
            this.dialog.closeAll();
        } else {
            await super.backToQuotation();
        }
    },
});

patch(ProductCatalogKanbanController, {
    template: "mrp_workorder.ProductCatalogKanbanController",
});
