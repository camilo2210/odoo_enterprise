import { ActionPanel } from "@mail/discuss/core/common/action_panel";

import { Component, t, useProps } from "@odoo/owl";

import { AiAgentPanel } from "@ai_agentic/discuss/core/web/ai_agent_panel/ai_agent_panel";

/** The agent panel as a thread action panel, for the chats opened outside the agent's page. */
export class AiAgentActionPanel extends Component {
    static template = "ai_agentic.AiAgentActionPanel";
    static components = { ActionPanel, AiAgentPanel };

    props = useProps({
        agent: t.any(),
        close: t.function().optional(),
    });
}
