import { DiscussClientAction } from "@mail/core/public_web/discuss_app/client_action";

import { t, useOnChange, useProps } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { router } from "@web/core/browser/router";

patch(DiscussClientAction.prototype, {
    setup() {
        super.setup(...arguments);
        this.updateActionState = useProps.static("updateActionState", t.function());
        useOnChange(
            () => [this.action(), router.current.scoped_ai_agent_id],
            (action) => this.syncScopedAiAgent(action)
        );
        // Keep the scoped agent id in the URL so it survives a reload with a different
        // `active_id`. And keep it on the action as well to be able to get back to the
        // scoped view from the breadcrumbs.
        useOnChange(
            () => [this.store.discuss.scopedAiAgentId],
            (scopedAiAgentId) => {
                this.updateActionState({ scoped_ai_agent_id: scopedAiAgentId });
                if (this.action()) {
                    this.action().context.scoped_ai_agent_id = scopedAiAgentId;
                }
            }
        );
        // Opening another AI chat re-scopes to its agent. Opening anything else leaves
        // the scoped view. A chat already in the current scope is left untouched above.
        useOnChange(
            () => [this.store.discuss.thread],
            (thread) => {
                if (
                    !thread ||
                    !this.store.discuss.scopedAiAgentId ||
                    this.store.discuss.isChannelInScopedAiAgent(thread.channel)
                ) {
                    return;
                }
                if (thread.channel?.ai_agent_id) {
                    this.store.discuss.setScopedAiAgent(thread.channel.ai_agent_id.id);
                } else {
                    this.store.discuss.clearScopedAiAgent();
                }
            },
            { initialRun: false }
        );
    },

    getScopedAiAgentIdFromAction(action) {
        const rawId = action?.context?.scoped_ai_agent_id || router.current.scoped_ai_agent_id;
        return rawId ? Number(rawId) : undefined;
    },

    syncScopedAiAgent(action) {
        const scopedAiAgentId = this.getScopedAiAgentIdFromAction(action);
        if (scopedAiAgentId) {
            this.store.discuss.setScopedAiAgent(scopedAiAgentId);
        } else {
            this.store.discuss.clearScopedAiAgent();
        }
    },
});
