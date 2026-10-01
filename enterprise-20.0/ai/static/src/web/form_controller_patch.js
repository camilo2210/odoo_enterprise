import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillDestroy, onMounted, useListener } from "@odoo/owl";
import { aiChannelBus } from "@ai/utils/ai_channel_bus";

patch(FormController.prototype, {
    setup() {
        super.setup();
        this.aiChatLauncher = useService("aiChatLauncher");
        const openAiChat = (ev) => this.openAiChat(ev.detail.origin);
        useListener(this.env.bus, "AI:OPEN_AI_CHAT", openAiChat);
        onMounted(() =>
            aiChannelBus.trigger("AI: Update Target Record", {
                recordModel: this.model.root.resModel,
                recordId: this.model.root.resId,
                targetRecord: this.model.root,
            })
        );
        onWillDestroy(() =>
            aiChannelBus.trigger("AI: Update Target Record", {
                targetRecord: undefined,
            })
        );
    },

    async openAiChat(interfaceKey) {
        // save to allow to get messages from backend
        if (!this.mailStore || !(await this.model.root.save())) {
            return;
        }
        const channel = await this.aiChatLauncher.launchAIChat({
            interfaceKey,
            channelTitle: this.displayName(),
            recordModel: this.model.root.resModel,
            recordId: this.model.root.resId,
            originalRecordData: this.model.root.data,
            originalRecordFields: this.model.root.fields,
            aiChatSourceId: this.model.root.resId,
            aiSpecialActions: this.aiSpecialActions,
        });
        channel.targetRecord = this.model.root;
    },

    get aiSpecialActions() {
        return {};
    },

    async onPagerUpdate({ offset, resIds }) {
        const result = await super.onPagerUpdate({ offset, resIds });
        aiChannelBus.trigger("AI: Update Target Record", {
            recordModel: this.model.root.resModel,
            recordId: this.model.root.resId,
            targetRecord: this.model.root,
        });
        return result;
    },
});
