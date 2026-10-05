import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";
import { aiChannelBus } from "@ai/utils/ai_channel_bus";
import {
    AI_WEBSITE_ELEMENT_SELECTION_COMMAND,
    isAiWebsiteBuilderChannel,
} from "../utils";
import { getData } from "@ai/utils/bus_data_getter";
import { setAiResponsePromise } from "@ai_website/ai_processing_state";

patch(Thread.prototype, {
    setup() {
        super.setup(...arguments);
        // IMPROVEMENT: Block the editor only during Website tool execution, rather than every AI exchange.
        this.onChange(
            () => [isAiWebsiteBuilderChannel(this.channel) && this.channel.isAiGenerating],
            (isGenerating) => {
                if (!isGenerating) {
                    return;
                }
                let active = true;
                let unblockBuilderUI;
                let resolveTurn;
                // Set the AiResponsePromise so that if we navigate to a new page while the
                // agent is still working, it will kepe the block up and remove it once the
                // worker is finished.
                setAiResponsePromise(new Promise((resolve) => (resolveTurn = resolve)));
                getData("htmlBuilder")
                    .catch(() => null) // The builder may not be loaded in this browser.
                    .then((builder) => {
                        if (active) {
                            unblockBuilderUI = builder?.blockBuilderUI(1_500);
                        }
                    });

                // Release when activity stops or this thread is removed.
                return () => {
                    active = false;
                    unblockBuilderUI?.();
                    resolveTurn();
                };
            },
        );
    },
    async post(body, postData = {}, extraData = {}) {
        if (isAiWebsiteBuilderChannel(this.channel)) {
            const prepareCommand = { type: "prepare_send" };
            aiChannelBus.trigger(AI_WEBSITE_ELEMENT_SELECTION_COMMAND, prepareCommand);
            if (prepareCommand.elementLabels?.length) {
                extraData = {
                    ...extraData,
                    context: {
                        ...extraData.context,
                        ai_website_element_labels: prepareCommand.elementLabels,
                    },
                };
            }
        }

        return super.post(body, postData, extraData);
    },
});
