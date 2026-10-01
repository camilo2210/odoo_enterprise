import {
    SocialPostMessageField,
    socialPostMessageField,
} from "@social/js/fields/social_post_message_field";
import { registry } from "@web/core/registry";

class SocialPostMessageFacebookField extends SocialPostMessageField {
    extractMentionData(mentionedUserName, option) {
        if (this.props.socialMediaType !== "facebook") {
            return super.extractMentionData(mentionedUserName, option);
        }
        return { id: option.userInfo.id, name: option.userInfo.name };
    }

    getMentionDisplayName({ userInfo }) {
        return `[${userInfo.id}]`;
    }
}

export const socialPostMessageFacebookField = {
    ...socialPostMessageField,
    component: SocialPostMessageFacebookField,
    extractProps() {
        const props = socialPostMessageField.extractProps(...arguments);
        props.socialMediaType = "facebook";
        props.allowDoubleSpace = true;
        return props;
    },
};

registry
    .category("fields")
    .add("social_post_message_facebook_field", socialPostMessageFacebookField);
