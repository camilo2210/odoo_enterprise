import { aiChannelDataRegistry } from "@ai/utils/ai_channel_data_registry";
import { DiscussChannel } from "@mail/discuss/core/common/discuss_channel_model";
import { fields } from "@mail/model/export";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").DiscussChannel} */
const discussChannelPatch = {
    setup() {
        super.setup(...arguments);
        this.ai_prompt_buttons = fields.Many("ai.prompt.button");
        this.ai_agent_id = fields.One("ai.agent");
        this.ai_session_ids = fields.Many("ai.session", { inverse: "channel_id" });
        this.onChange(
            () => [...this.ai_session_ids],
            function onChangeAiSessions() {
                this.aiRootSession?.syncAiSessionState();
            },
            { immediate: true, initialRun: false },
        );
        this.aiInputSession = fields.One("ai.session");
        this.isAiGenerating = false;
        this.isAiSubmitting = false;
        this.suggestedAiChannel = fields.One("discuss.channel");
        /** @type {number|undefined} record the AI chat was started from */
        this.aiChatSource = undefined;
        /** @type {Object|undefined} actions offered by the caller of the AI chat */
        this.aiSpecialActions = undefined;
        /** @type {Object|undefined} */
        this.targetRecord = undefined;
        /** @type {Object|undefined} */
        this.textSelection = undefined;
        /** @type {Object|undefined} actions the AI chat disables on its thread */
        this.disabledActions = undefined;
        /** @type {boolean|undefined} AI chat opened from a shop extra-image media dialog */
        this.fromShopExtraImage = undefined;
        this.are_prompts_from_local_storage = true;
        this.onChange(
            () => [this.are_prompts_from_local_storage],
            function onChangeArePromptsFromLocalStorage(arePromptsFromLocalStorage) {
                if (arePromptsFromLocalStorage) {
                    this._restorePrompts();
                } else {
                    this._savePrompts();
                }
            },
            { immediate: true, initialRun: false },
        );
        /** @type {Array<{id: number, name: string}>} */
        this.serializedPrompts = this.computed(() => {
            const prompts = this.ai_prompt_buttons.map((button) => ({
                id: button.id,
                name: button.name,
            }));
            return prompts.length > 0 ? prompts : undefined;
        });
        this.onChange(
            () => [this.serializedPrompts],
            function onChangeSerializedPrompts() {
                if (!this.are_prompts_from_local_storage) {
                    this._savePrompts();
                }
            },
            { immediate: true, initialRun: false },
        );
        /**
         * Prompt buttons to save on the local storage.
         * Channels are synchronized with bus but random prompts are contextual and not stored on
         * the database/not linked to the channel so they need to be saved in localStorage for
         * proper sync cross-tab and to restore them after page refresh.
         * This implies multi-device is not supported.
         * They can be deleted when the channel is closed/locally deleted/no longer accessed.
         *
         * @type {Array<{id: number, name: string}>}
         */
        this.localStoragePrompts = this.localStorage(undefined);
        this.onChange(
            () => [this.localStoragePrompts],
            function onChangeLocalStoragePrompts() {
                if (this.are_prompts_from_local_storage) {
                    this._restorePrompts();
                }
            },
            { immediate: true },
        );
    },
    get aiRootSession() {
        return this.ai_session_ids.find((session) => !session.parent_session_id);
    },
    get computedDisplayName() {
        const displayName = super.computedDisplayName;
        if (this.isAiChat && !this.name && this.ai_agent_id) {
            return this.ai_agent_id.name;
        }
        return displayName;
    },
    get isAiChat() {
        return this.channel_type === "ai_chat";
    },
    get aiSession() {
        return this.aiRootSession;
    },
    get aiMember() {
        return this.channel_member_ids?.find((member) => member.isAiAgent);
    },
    get chatChannelTypes() {
        // overridden to show the last message of the ai chats in the messaging menu
        // and show the count of AI chats with unread messages
        return [...super.chatChannelTypes, "ai_chat"];
    },
    get showUnreadBanner() {
        if (this.isAiChat) {
            const newestMessage = this.newestPersistentMessage;
            if (newestMessage?.aiIsAgentStep || newestMessage?.aiIsToolUse) {
                return false;
            }
        }
        return super.showUnreadBanner;
    },
    get importantCounter() {
        if (this.isAiChat) {
            const newestMessage = this.newestPersistentMessage;
            if (newestMessage?.aiIsAgentStep || newestMessage?.aiIsToolUse) {
                return 0;
            }
        }
        return super.importantCounter;
    },
    async deleteAiChatRpc() {
        const channelId = this.id;
        await this.store.env.services.orm.silent.call("discuss.channel", "unlink", [channelId]);
        aiChannelDataRegistry.removeData(channelId);
    },
    _restorePrompts() {
        this.ai_prompt_buttons = this.localStoragePrompts;
    },
    _savePrompts() {
        this.localStoragePrompts = this.serializedPrompts;
    },
};
patch(DiscussChannel.prototype, discussChannelPatch);
