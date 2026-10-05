import { useService } from "@web/core/utils/hooks";
import { Component, onPatched, signal, t, useProps } from "@odoo/owl";

export class AgentToolSummary extends Component {
    static template = "ai.AgentToolSummary";

    setup() {
        super.setup();
        this.store = useService("mail.store");
        this.orm = useService("orm");
        this.props = useProps({
            message: t.instanceOf(this.store["mail.message"]),
            onAfterToggle: t.function(),
            onBeforeToggle: t.function(),
        });
        this.isUnfolded = signal(false);
        this.toolParams = undefined;
        onPatched(() => this.props.onAfterToggle());
    }

    get toolCallId() {
        return this.props.message.bodyEl?.querySelector(".o-ai-tool-summary")?.dataset.id;
    }

    async loadParams() {
        const eventId = this.props.message.bodyEl?.querySelector(".o-ai-agent-step")?.dataset.id;
        if (!eventId) {
            return;
        }
        const callId = this.toolCallId;
        if (!callId) {
            return;
        }
        const toolParams = await this.orm.call("ai.session.event", "get_tool_params", [
            Number(eventId),
            callId,
        ]);
        this.toolParams = toolParams;
    }

    async onClickMessage() {
        if (!this.toolParams) {
            await this.loadParams();
        }
        this.props.onBeforeToggle();
        this.isUnfolded.set(!this.isUnfolded());
    }

    stringify(value) {
        if (typeof value === "object" || value === "") {
            return JSON.stringify(value);
        }
        return value;
    }
}
