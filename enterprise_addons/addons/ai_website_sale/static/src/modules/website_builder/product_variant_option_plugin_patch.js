import { patch } from "@web/core/utils/patch";
import { ProductAddImageAction } from "@website_sale/website_builder/product_variant_option_plugin";
import { TABS } from "@html_editor/main/media/media_dialog/media_dialog_utils";

patch(ProductAddImageAction.prototype, {
    getMediaDialogProps({ editingElement, loadPromiseResolveFunction }) {
        const props = super.getMediaDialogProps({ editingElement, loadPromiseResolveFunction });
        const { model, productProductID: productID, productTemplateID: templateID } = this;
        const resID = parseInt(model === "product.product" ? productID : templateID);
        return {
            ...props,
            reloadEditorAfterSave: true,
            originalRecordModel: model,
            originalRecordId: resID,
            fromShopExtraImage: true,
            aiSave: async (imgEl, selectedMedia, activeTab) => {
                if (selectedMedia.length > 0) {
                    const type = activeTab === TABS["IMAGES"].id ? "image" : "video";
                    await this.apply({ editingElement, loadResult: { imgEls: [imgEl], selectedMedia, type } })
                }
            },
        };
    },
});
