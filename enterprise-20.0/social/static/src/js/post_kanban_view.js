import { useListener } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { MediaCarouselDialog } from "./media_carousel_dialog";

export class PostKanbanRenderer extends KanbanRenderer {
    setup() {
        super.setup();

        this.dialog = useService("dialog");
        // capture phase: the handler stops the propagation to prevent the card's
        // global click, which is bound on the record root, i.e. below this one.
        useListener(
            this.rootRef,
            "click",
            (ev) => {
                const imageEl = ev.target.closest(".o_social_stream_post_content_more");
                if (imageEl) {
                    this.onClickMoreImages(ev, imageEl);
                }
            },
            { capture: true }
        );
    }

    /**
     * Shows a bootstrap carousel starting at the clicked image's index
     *
     * @param {PointerEvent} ev - event of the clicked image
     * @param {HTMLElement} imageEl - the clicked image
     */
    onClickMoreImages(ev, imageEl) {
        ev.stopPropagation();
        this.dialog.add(MediaCarouselDialog, {
            title: _t("Post Images"),
            activeIndex: parseInt(imageEl.dataset.index),
            medias: imageEl.dataset.imageUrls
                .split(",")
                .map((data) => ({ type: "image", url: data })),
        });
    }
}

export const PostKanbanView = {
    ...kanbanView,
    Renderer: PostKanbanRenderer,
};

registry.category("views").add("social_post_kanban_view", PostKanbanView);
