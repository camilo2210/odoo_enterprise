/** @odoo-module **/

import { AgentSourceAddDialog } from "@ai_agentic/components/agent_add_source_dialog/agent_add_source_dialog";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(AgentSourceAddDialog.prototype, {
    get cardsData() {
        return [
            ...super.cardsData,
            {
                image: "/ai_agentic_knowledge/static/img/icon.png",
                title: _t("Add from Knowledge"),
                onClick: () => this.onAddKnowledgeSourceClick(),
            },
        ];
    },

    onAddKnowledgeSourceClick() {
        const onSourcesAdded = this.props.onSourcesAdded;
        this.props.close();
        return this.actionService.doAction("ai_knowledge.action_ai_add_knowledge_articles", {
            additionalContext: {
                default_agent_id: this.agentId,
            },
            onClose: async (closeInfo) => {
                if (closeInfo?.sourcesAdded) {
                    await onSourcesAdded();
                }
            },
        });
    },
});
