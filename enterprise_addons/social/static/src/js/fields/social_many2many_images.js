import { MediaCarouselDialog } from "../media_carousel_dialog";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Component for a many2many field to <social.post.image>, containing only images.
 */
export class SocialMany2manyImages extends Component {
    static template = "social.SocialMany2manyImages";

    props = useProps(standardFieldProps);

    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    get attachmentsIds() {
        return this.props.record.data[this.props.name].records.map((record) => record.resId);
    }

    onClickMoreImages() {
        this.dialog.add(MediaCarouselDialog, {
            title: _t("Post Images"),
            activeIndex: 0,
            medias: this.attachmentsIds.map((attachmentId) => ({
                type: "image",
                url: `/web/image/social.post.image/${attachmentId}/raw`,
            })),
        });
    }
}

export const socialMany2manyImages = {
    component: SocialMany2manyImages,
    supportedTypes: ["many2many"],
    relatedFields: () => [{ name: "id", type: "integer" }],
};

registry.category("fields").add("social_many2many_images", socialMany2manyImages);
