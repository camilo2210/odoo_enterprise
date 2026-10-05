import { useSubEnv } from "@web/owl2/utils";
import { ProductCatalogKanbanRecord } from "@product/product_catalog/kanban_record";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

export class FSMProductCatalogKanbanRecord extends ProductCatalogKanbanRecord {
    setup() {
        super.setup();
        this.orm = useService("orm");
        useSubEnv({
            ...this.env,
            intervention_id: this.props.record.context.intervention_id || this.props.record.context.active_id,
            resetQuantity: this.debouncedUpdateQuantity.bind(this),
        });
    }

    async _onQuantityChange() {
        const { action, price, min_quantity, subtotal } = await rpc(
            "/product/catalog/update_order_line_info",
            {
                order_id: this.env.orderId || false,
                product_id: this.env.productId,
                quantity: this.productCatalogData.quantity,
                res_model: this.env.orderResModel,
                intervention_id: this.env.intervention_id,
                child_field: this.env.childField,
                section_id: this.env.selectedSectionId,
                uom_id: this.productCatalogData.uomId,
            }
        );
        if (price) {
            this.productCatalogData.price = parseFloat(price);
        }
        if (min_quantity) {
            this.productCatalogData.minimumQuantityOnProduct = min_quantity;
        }
        let subtotalDelta = 0;
        if (subtotal) {
            const parsedSubtotal = parseFloat(subtotal);
            subtotalDelta = parsedSubtotal - this.productCatalogData.subtotal;
            this.productCatalogData.subtotal = parsedSubtotal;
        }
        if (subtotalDelta) {
            this.notifySectionSubtotalChange(subtotalDelta);
        }
        if (action && action !== true) {
            const actionContext = {
                default_product_id: this.props.record.data.id,
            };
            const options = {
                additionalContext: actionContext,
                onClose: async (closeInfo) => {
                    const domain = [
                        ["planning_slot_id", "=", this.env.intervention_id],
                        ["product_id", "=", this.env.productId],
                        ["product_uom_qty", ">", 0],
                    ];
                    let lines = await this.orm.searchRead("sale.order.line", domain, [
                        "product_uom_qty",
                        "parent_id",
                    ]);
                    if (this.env.orderId) {
                        lines = lines.filter((line) =>
                            this.env.searchModel.selectedSectionId
                                ? line.parent_id?.[0] == this.env.searchModel.selectedSectionId
                                : line.parent_id == false
                        );
                    }
                    const quantity = lines.reduce((total, line) => total + line.product_uom_qty, 0);
                    this.productCatalogData.quantity = quantity;
                    this.productCatalogData.tracking = true;
                },
            };
            await this.action.doAction(action, options);
        }
    }
}
