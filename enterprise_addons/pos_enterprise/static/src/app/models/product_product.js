import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";

// Not using the POS product model to avoid loading additional dependencies.
// We can use it if we need more of its methods in future.
export class ProductProduct extends Base {
    static pythonModel = "product.product";

    get parentPosCategIds() {
        const current = [];
        const categories = this.pos_categ_ids;
        const getParent = (categ) => {
            const parentCat = categ.parent_id;
            if (parentCat) {
                current.push(parentCat.id);
                getParent(parentCat);
            }
        };
        for (const category of categories) {
            current.push(category.id);
            getParent(category);
        }
        return current;
    }
}

registry.category("pos_available_models").add(ProductProduct.pythonModel, ProductProduct);
