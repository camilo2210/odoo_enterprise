import { Dialog } from "@web/core/dialog/dialog";
import { Component, t, useProps } from "@odoo/owl";

export class MediaCarouselDialog extends Component {
    static components = { Dialog };
    static template = "social.MediaCarouselDialog";

    props = useProps({
        title: t.string(),
        medias: t.array(),
        activeIndex: t.number(),
        close: t.function(),
        mediaType: t.string().optional(), // for twitter
    });
}
