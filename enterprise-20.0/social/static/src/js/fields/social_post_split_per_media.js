import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class SocialPostSplitPerMedia extends Component {
    static template = "social.SocialPostSplitPerMedia";

    props = useProps(standardFieldProps);

    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async onClick() {
        // copy the image so, the social media don't share the same order
        const toUpdate = await this.orm.call("social.post.template", "action_copy_images", [
            this.props.record.data.image_ids._currentIds,
        ]);
        for (const field in toUpdate) {
            await this.props.record.data[field].clear();
            await this.props.record.data[field].set(toUpdate[field]);
        }

        await this.props.record.update({ [this.props.name]: true });
    }
}

export const socialPostSplitPerMedia = {
    component: SocialPostSplitPerMedia,
    supportedTypes: ["boolean"],
};

registry.category("fields").add("social_post_split_per_media", socialPostSplitPerMedia);
