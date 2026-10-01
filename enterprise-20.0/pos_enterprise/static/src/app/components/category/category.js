import { Component, useProps, t } from "@odoo/owl";
import { usePrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import { PosCategory } from "@point_of_sale/app/models/pos_category";
import { roundQuantity } from "@pos_enterprise/app/utils/utils";

export class Category extends Component {
    static template = "pos_enterprise.Category";
    props = useProps({
        category: t.instanceOf(PosCategory),
    });

    setup() {
        this.prepDisplay = usePrepDisplay();
        this.products = [];
        this.productCount = 0;
    }

    get shouldShowCategory() {
        const category = this.props.category;
        const selectedStageId = this.prepDisplay.selectedStageId;
        const products = {};

        this.productCount = 0;

        for (const prepLine of category.prepLines) {
            if (prepLine.isStageDone()) {
                continue;
            }
            if (prepLine.stage_id.id === selectedStageId || !selectedStageId) {
                const quantity = prepLine.quantity;
                const cancelled = prepLine.cancelled;

                if (!products[prepLine.product.id]) {
                    products[prepLine.product.id] = {
                        id: prepLine.product.id,
                        name: prepLine.product_id.display_name,
                        categoryIds: prepLine.categories.map((categ) => categ.id),
                        quantity: quantity,
                        cancelled: cancelled,
                    };
                } else {
                    products[prepLine.product.id].quantity += quantity;
                    products[prepLine.product.id].cancelled += cancelled;
                }

                this.productCount += prepLine.quantity - prepLine.cancelled;
            }
            if (
                !products[prepLine.product.id] &&
                this.prepDisplay.selectedProductIds.has(prepLine.product.id)
            ) {
                products[prepLine.product.id] = {
                    id: prepLine.product.id,
                    name: prepLine.product_id.display_name,
                    categoryIds: prepLine.categories.map((categ) => categ.id),
                    quantity: 0,
                    cancelled: 0,
                };
            }
        }

        const models = this.prepDisplay.data.models;
        this.productCount = roundQuantity(this.productCount, models);
        for (const product of Object.values(products)) {
            product.quantity = roundQuantity(product.quantity, models);
            product.cancelled = roundQuantity(product.cancelled, models);
            product.todoQuantity = roundQuantity(product.quantity - product.cancelled, models);
        }

        this.products = Object.values(products).sort((a, b) => b.quantity - a.quantity);
        return this.products.length;
    }
}
