import { aiChannelBus } from "@ai/utils/ai_channel_bus";
import { AgentToolSummary } from "@ai/discuss/agent_tool_summary";
import { Thread } from "@mail/core/common/thread";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";

import { signal } from "@odoo/owl";

Thread.components = { ...Thread.components, AgentToolSummary };
patch(Thread.prototype, {
    setup() {
        super.setup();
        this.aiStepsGroupsVisibility = signal.Map();
        if (this.props.thread.channel?.isAiChat) {
            useBus(aiChannelBus, "AI: Update Target Record", ({ detail }) => {
                const recordModel = detail.recordModel;
                const recordId = detail.recordId;
                if (
                    detail.targetRecord &&
                    this.props.thread.channel.aiRootSession.res_model === recordModel &&
                    this.props.thread.channel.aiRootSession.res_id === recordId
                ) {
                    this.props.thread.channel.targetRecord = detail.targetRecord;
                    this.props.thread.channel.aiSpecialActions = {
                        ...this.props.thread.channel.aiSpecialActions,
                        ...this.props.thread.channel.disabledActions,
                    };
                    this.props.thread.channel.disabledActions = {};
                } else {
                    const { product_main_image, product_extra_image, ...remainingActions } =
                        this.props.thread.channel.aiSpecialActions || {};
                    const disabledActions = {};
                    if (product_main_image) {
                        disabledActions.product_main_image = product_main_image;
                    }
                    if (product_extra_image) {
                        disabledActions.product_extra_image = product_extra_image;
                    }
                    this.props.thread.channel.disabledActions = disabledActions;
                    this.props.thread.channel.aiSpecialActions = remainingActions;
                }
            });
            useBus(aiChannelBus, "AI: Drop UseThis Action", () => {
                // ProductAddExtraImageAction reloads the editor after save which causes the useThis button to be removed.
                // We want to avoid that because the useThis button doesn't rely on the editor for saving in that specific case.
                if (this.props.thread.channel.fromShopExtraImage) {
                    return;
                }
                const actions = this.props.thread.channel.aiSpecialActions || {};
                delete actions.useThis;
            });
        }
    },
    get startMessageChannelTypes() {
        return [...super.startMessageChannelTypes, "ai_chat"];
    },
    get startMessageSubtitle() {
        if (this.channel?.isAiChat) {
            return this.channel.ai_agent_id?.subtitle || _t("Hello, what can I help you with?");
        } else {
            return super.startMessageSubtitle;
        }
    },
    onClickPromptButton(button) {
        this.props.thread.post(button.name, {}, { ai_prompt_button_ref: button.id });
    },
    get showPromptButtons() {
        return this.props.thread.messages.length === 0;
    },
    get sortedPromptButtons() {
        return (this.channel?.ai_prompt_buttons || []).sort((a, b) => a.sequence - b.sequence);
    },
    isSquashed(msg, prevMsg) {
        if (msg.aiAgentAuthored) {
            // author and date are added when starting a steps group
            return true;
        }
        return super.isSquashed(...arguments);
    },
    isStepsGroupShown(groupId) {
        return (
            this.aiStepsGroupsVisibility().get(groupId) ??
            (this.channel.aiSession?.config["show_agent_steps"] ||
                !!this.props.thread.store.debugMode.isActive())
        );
    },
    preserveScrollPosition() {
        this.props.thread.scrollTop = this.scrollableRef().scrollTop;
        this.lastSetValue = undefined;
    },
    toggleStepsGroupVisibility(groupId, preserveScroll = true) {
        if (preserveScroll) {
            this.preserveScrollPosition();
        }
        this.aiStepsGroupsVisibility().set(groupId, !this.isStepsGroupShown(groupId));
    },
    showNewMessageLine(msg, prevMsg) {
        // only show it for the final response
        return !msg.aiIsAgentStep && super.showNewMessageLine(...arguments);
    },
});
