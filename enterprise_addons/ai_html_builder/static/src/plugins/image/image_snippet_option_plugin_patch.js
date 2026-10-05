import { patch } from "@web/core/utils/patch";
import { ImageSnippetOptionPlugin } from "@html_builder/plugins/image/image_snippet_option_plugin";

patch(ImageSnippetOptionPlugin.prototype, {
    getMediaDialogProps(snippetEl, dragState) {
        const params = super.getMediaDialogProps(snippetEl, dragState);
        params.aiBeforeCloseHandler = (channelId) => {
            const { width, height } = snippetEl.getBoundingClientRect();

            const img = document.createElement("img");
            img.src = "/ai/static/description/icon_hi.png";
            img.classList.add("img-fluid", "o_we_custom_image");
            img.dataset.aiChannelId = channelId;
            img.style.width = `${width}px`;
            img.style.height = `${height}px`;

            snippetEl.replaceWith(img);
            // If the "Image" snippet was dropped as a grid item, make
            // it a grid image.
            if (dragState.draggedEl.classList.contains("o_grid_item")) {
                dragState.draggedEl.classList.add("o_grid_item_image");
            }
            dragState.replacedSnippetEl = img;
            this.trigger("on_media_replaced_handlers", { newMediaEl: img });
        };
        const oldSave = params.save;
        const newSave = async (...args) => {
            await oldSave(...args);
            const selectedImageEl = args[0];
            this.trigger("on_media_replaced_handlers", { newMediaEl: selectedImageEl });
        };
        params.save = newSave;
        return params;
    },

});
