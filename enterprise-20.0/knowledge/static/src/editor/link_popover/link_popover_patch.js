import { LinkPopover } from "@html_editor/main/link/link_popover";
import { ARTICLE_LINKS_SELECTOR } from "@knowledge/editor/plugins/article_plugin/article_plugin";
import { patch } from "@web/core/utils/patch";

// Patch to show cover image in link preview for internal knowledge article links
// and to hide URL for such links.
patch(LinkPopover.prototype, {
    async loadAsyncLinkPreview() {
        await super.loadAsyncLinkPreview();
        const url = URL.parse(this.state.url, this.props.document.URL);

        if (url && url.hostname === window.location.hostname) {
            const metaData = await this.props.getInternalMetaData(url.href).catch((error) => ({}));
            if (metaData?.preview_image_url) {
                this.state.imgSrc = metaData.preview_image_url;
            }
        }

    },
    get showUrl() {
        if (this.props.linkElement?.matches(ARTICLE_LINKS_SELECTOR)) {
            return false;
        }
        return super.showUrl;
    },
});
