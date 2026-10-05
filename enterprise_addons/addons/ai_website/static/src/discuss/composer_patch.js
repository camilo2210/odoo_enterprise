import { Composer } from "@mail/core/common/composer";
import { ComposerAction, registerComposerAction } from "@mail/core/common/composer_actions";
import { onMounted, proxy } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";
import { aiChannelBus } from "@ai/utils/ai_channel_bus";
import {
    AI_WEBSITE_ELEMENT_SELECTION_COMMAND,
    AI_WEBSITE_ELEMENT_SELECTION_STATE,
    isAiWebsiteBuilderChannel,
} from "@ai_website/utils";

patch(ComposerAction.prototype, {
    _getAiComposerActions() {
        return [...super._getAiComposerActions(), "select-element"];
    },
});

patch(Composer.prototype, {
    setup() {
        super.setup();
        this.aiWebsiteSelectionState = proxy({
            available: false,
            pickerActive: false,
            elements: [],
        });
        if (isAiWebsiteBuilderChannel(this.thread?.channel)) {
            useBus(aiChannelBus, AI_WEBSITE_ELEMENT_SELECTION_STATE, ({ detail }) => {
                Object.assign(this.aiWebsiteSelectionState, detail);
            });
            onMounted(() => {
                aiChannelBus.trigger(AI_WEBSITE_ELEMENT_SELECTION_COMMAND, {
                    type: "request_state",
                });
            });
        }
    },
    deselectAiWebsiteElement(id) {
        aiChannelBus.trigger(AI_WEBSITE_ELEMENT_SELECTION_COMMAND, {
            type: "deselect",
            id,
        });
    },
    getAiWebsiteElementRemoveLabel(element) {
        return _t("Remove %(element)s", { element: element.label });
    },
});

registerComposerAction("select-element", {
    condition: ({ owner }) => owner.aiWebsiteSelectionState.available,
    disabledCondition: ({ owner }) => owner.isAiAgentGenerating,
    icon: "pan_tool_alt",
    isActive: ({ owner }) => owner.aiWebsiteSelectionState.pickerActive,
    name: _t("Select Elements"),
    onSelected: () => {
        aiChannelBus.trigger(AI_WEBSITE_ELEMENT_SELECTION_COMMAND, {
            type: "toggle_picker",
        });
    },
    sequence: 30,
});
