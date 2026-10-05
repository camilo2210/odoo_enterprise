import { patch } from "@web/core/utils/patch";
import { ProductImageFieldWithMediaDialog } from "@ai_product/modules/html_editor/fields/product_image_field_with_media_dialog";
import { product_extra_image_action } from "@ai_website_sale/modules/web/product_ai_actions";

patch(ProductImageFieldWithMediaDialog.prototype, {
    get aiSpecialActions() {
        const actions = super.aiSpecialActions;
        if (["product.template", "product.product"].includes(this.props.record._config.resModel)) {
            actions.product_extra_image = product_extra_image_action();
        }
        return actions;
    },
});
