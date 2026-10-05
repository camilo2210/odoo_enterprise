import { registry } from "@web/core/registry";
import {
    ImageFieldWithMediaDialog,
    imageFieldWithMediaDialog,
} from "@html_editor/fields/image_field_with_media_dialog/image_field_with_media_dialog";
import { product_main_image_action } from "@ai_product/modules/web/product_ai_actions";

export class ProductImageFieldWithMediaDialog extends ImageFieldWithMediaDialog {
    get aiSpecialActions() {
        const actions = super.aiSpecialActions;
        if (["product.template", "product.product"].includes(this.props.record._config.resModel)) {
            actions.product_main_image = product_main_image_action();
        }
        return actions;
    }
}

export const productImageFieldWithMediaDialog = {
    ...imageFieldWithMediaDialog,
    component: ProductImageFieldWithMediaDialog,
};

registry
    .category("fields")
    .add("product_image_with_media_dialog", productImageFieldWithMediaDialog);
