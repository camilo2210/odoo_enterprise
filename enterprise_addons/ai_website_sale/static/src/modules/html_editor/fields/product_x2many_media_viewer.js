import { patch } from "@web/core/utils/patch";
import { ProductX2ManyMediaViewer } from "@ai_product/modules/html_editor/fields/product_x2many_media_viewer";
import { product_extra_image_action } from "@ai_website_sale/modules/web/product_ai_actions";

patch(ProductX2ManyMediaViewer.prototype, {
    get aiSpecialActions(){
        const actions = super.aiSpecialActions;
        if (["product.template", "product.product"].includes(this.props.record._config.resModel)) {
            actions.product_extra_image = product_extra_image_action();
        }
        return actions;
    }
})
