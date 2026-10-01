import { Discuss } from "@mail/core/public_web/discuss_app/discuss_app";

import { AiAgentPanel } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";

Discuss.components = { ...Discuss.components, AiAgentPanel };

patch(Discuss.prototype, {
    get showScopedAgentPanel() {
        return Boolean(this.store.discuss.scopedAgent) && user.isSystem && !this.ui.isSmall;
    },
});
