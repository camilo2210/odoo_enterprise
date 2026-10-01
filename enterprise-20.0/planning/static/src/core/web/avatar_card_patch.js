import { AvatarCard } from "@mail/core/web/avatar_card/avatar_card";

import { BadgeTag } from "@web/core/tags_list/badge_tag";
import { TagsList } from "@web/core/tags_list/tags_list";
import { patch } from "@web/core/utils/patch";

Object.assign(AvatarCard.components, { BadgeTag, TagsList });

/** @type {AvatarCard} */
const avatarCardPatch = {
    get roleTags() {
        return (
            this.resource?.role_ids.map(({ id, color, name }) => ({
                id,
                color,
                text: name,
                hasIcon:
                    id === this.resource.default_role_id?.id && this.resource.role_ids.length > 1,
            })) ?? []
        );
    },
    /** @override */
    get hasFooter() {
        return this.roleTags.length > 0 || super.hasFooter;
    },
};
export const unpatchAvatarCard = patch(AvatarCard.prototype, avatarCardPatch);
