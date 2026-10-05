import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { SocialPostMessageField } from "@social/js/fields/social_post_message_field";

patch(SocialPostMessageField.prototype, {
    setup() {
        super.setup();
        this.aiChatLauncher = useService("aiChatLauncher");
    },

    async onAiClick() {
        const data = {
            field_name: `You are writing on this field: ${this.props.name}`,
            accounts: this.props.record.data.account_ids.records.map((r) => r.data.display_name),
            post_size_limit: this.props.record.data.max_post_length_per_media,
            current_post_content: this.props.record.data[this.props.name],
        };
        if (this.props.socialMediaType) {
            data.media = `You are writing a post for ${this.props.socialMediaType} specifically`;
        }

        await this.aiChatLauncher.launchAIChat({
            interfaceKey: "text_field_social",
            context: { ai_social_post_values: data },
            aiSpecialActions: {
                insert: async (content) => {
                    // remove the web sources before inserting
                    const contentToInsert = content.cloneNode(true);
                    for (const link of contentToInsert.querySelectorAll("a")) {
                        link.remove();
                    }

                    let oldContent = this.props.record.data[this.props.name] || "";
                    if (oldContent.length) {
                        oldContent += " ";
                    }

                    await this.props.record.update({
                        [this.props.name]: oldContent + contentToInsert.textContent,
                    });
                    this.messageValue.set(oldContent + contentToInsert.textContent);
                },
                selectPreviousInsertion: (selectionId) => false,
            },
            channelTitle: _t("Social Post Editor"),
            aiChatSourceId: this.props.record.id,
        });
    },
});
