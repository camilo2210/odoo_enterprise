import { Component, t, useProps } from "@odoo/owl";

/** One clickable option in a "how do you want to do this?" dialog. */
export class AiAgentPanelCard extends Component {
    static template = "ai_agentic.AiAgentPanelCard";

    props = useProps({
        icon: t.string().optional(),
        image: t.string().optional(),
        title: t.string(),
        description: t.string().optional(),
        onClick: t.function(),
    });
}
