import { AiAgent } from "@ai/discuss/core/common/ai_agent_model";

import { patch } from "@web/core/utils/patch";

patch(AiAgent.prototype, {
    setup() {
        super.setup(...arguments);
        /** Whether inspectable automation runs exist, feeding the scoped Automation tab. */
        this.has_automation_channels = false;
    },
});
