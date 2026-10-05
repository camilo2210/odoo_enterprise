import { useListener } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { KanbanHeader } from "@web/views/kanban/kanban_header";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { useService } from "@web/core/utils/hooks";

import { StreamPostKanbanRecord } from "./stream_post_kanban_record";
import { MediaCarouselDialog } from "./media_carousel_dialog";

class StreamPostKanbanHeader extends KanbanHeader {
    static template = "social.KanbanHeader";
}

export class StreamPostKanbanRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: StreamPostKanbanRecord,
        KanbanHeader: StreamPostKanbanHeader,
    };
    setup() {
        super.setup();

        this.dialog = useService("dialog");
        useListener(this.rootRef, "click", (ev) => {
            const mediaEl = ev.target.closest("a.o_social_stream_post_content_more");
            if (mediaEl) {
                this.onClickMoreAttachment(ev, mediaEl);
            }
        });
    }

    /**
     * Shows a bootstrap carousel starting at the clicked attachment's index
     *
     * @param {PointerEvent} ev - event of the clicked attachment
     * @param {HTMLElement} mediaEl - the clicked attachment
     */
    onClickMoreAttachment(ev, mediaEl) {
        ev.stopPropagation();
        this.dialog.add(MediaCarouselDialog, {
            title: _t("Post Medias"),
            activeIndex: parseInt(mediaEl.dataset.index),
            medias: JSON.parse(mediaEl.dataset.contentJson),
            mediaType: mediaEl.dataset.mediaType,
        });
    }

    /**
     * Always display the no-content helper, even if there are groups.
     */
    get showNoContentHelper() {
        const { model } = this.props.list;
        return !model.hasData();
    }
}
