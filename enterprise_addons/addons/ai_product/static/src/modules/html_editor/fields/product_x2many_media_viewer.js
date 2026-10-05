import { registry } from "@web/core/registry";
import { X2ManyMediaViewer, x2ManyMediaViewer } from "@html_editor/fields/x2many_field/x2many_media_viewer";
import { product_main_image_action } from "@ai_product/modules/web/product_ai_actions";


export class ProductX2ManyMediaViewer extends X2ManyMediaViewer {
    get aiSpecialActions(){
        const actions = super.aiSpecialActions;
        if (["product.template", "product.product"].includes(this.props.record._config.resModel)) {
            actions.product_main_image = product_main_image_action();
        }
        return actions;
    }
}

export const productX2ManyMediaViewer = {
    ...x2ManyMediaViewer,
    component: ProductX2ManyMediaViewer,
};

registry.category("fields").add("product_x2many_media_viewer", productX2ManyMediaViewer);

