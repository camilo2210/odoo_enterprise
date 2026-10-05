import {
    SocialPostMessageField,
    socialPostMessageField,
} from "@social/js/fields/social_post_message_field";
import { registry } from "@web/core/registry";

export class SocialPostMessageLinkedinField extends SocialPostMessageField {
    setup() {
        super.setup();
        this.optionTemplate = "social.LinkedinMentionsTemplate";
    }

    extractMentionData(mentionedUserName, option) {
        if (this.props.socialMediaType !== "linkedin") {
            return super.extractMentionData(mentionedUserName, option);
        }
        return {
            full_name: option.userInfo.full_name,
            member: option.userInfo.member,
            vanity_name: option.userInfo.vanity_name,
        };
    }
    getMentionDisplayName(option) {
        return option.userInfo.vanity_name;
    }
}

export const socialPostMessageLinkedinField = {
    ...socialPostMessageField,
    component: SocialPostMessageLinkedinField,
    extractProps() {
        const props = socialPostMessageField.extractProps(...arguments);
        props.socialMediaType = "linkedin";
        return props;
    },
};

registry
    .category("fields")
    .add("social_post_message_linkedin_field", socialPostMessageLinkedinField);
