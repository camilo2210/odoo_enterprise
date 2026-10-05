import { DiscussChannel as LivechatDiscussChannel } from "@im_livechat/../tests/mock_server/mock_models/discuss_channel";

export class DiscussChannel extends LivechatDiscussChannel {
    _store_channel_fields(res) {
        super._store_channel_fields(res);
        const DiscussChannelMember = this.env["discuss.channel.member"];
        const MailGuest = this.env["mail.guest"];
        const SocialAccount = this.env["social.account"];

        const customerGuests = (channel) =>
            MailGuest.browse(
                DiscussChannelMember.browse(channel.channel_member_ids)
                    .filter((member) => member.livechat_member_type === "visitor")
                    .map((member) => member.guest_id)
                    .filter(Boolean)
            );
        res.one(
            "livechat_social_account_id",
            (res) => {
                res.attr("name");
                res.one("media_id", ["id"]);
            },
            { sudo: true }
        );
        res.attr("livechat_failure");
        res.many("livechat_customer_guest_ids", ["id"], {
            sudo: true,
            value: customerGuests,
        });
        res.attr(
            "social_account_image_url",
            (channel) => `/web/image/social.account/${channel.livechat_social_account_id}/image`
        );
        res.attr("social_account_media_image_url", (channel) => {
            const [account] = SocialAccount.browse(channel.livechat_social_account_id);
            return `/web/image/social.media/${account?.media_id}/image`;
        });
    }
}
