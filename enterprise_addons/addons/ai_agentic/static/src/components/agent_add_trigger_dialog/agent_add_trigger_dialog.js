import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { AiAgentPanelCard } from "@ai_agentic/components/ai_agent_panel_card/ai_agent_panel_card";

const HELP_PROMPT = _t(
    "Let's create a new Trigger together, I'm not sure what setup is best for my use case."
);

export class AgentTriggerAddDialog extends Component {
    static template = "ai_agentic.AgentTriggerAddDialog";
    static components = { AiAgentPanelCard, Dialog };

    props = useProps({
        agentId: t.number(),
        close: t.function(),
    });

    setup() {
        this.action = useService("action");
        this.store = useService("mail.store");
        this.dialog = useService("dialog");
    }

    get cardsData() {
        return [
            {
                image: "/ai_agentic/static/src/img/ai_trigger_cron.svg",
                title: _t("On a Schedule"),
                description: _t("Run automatically at a set frequency, e.g. on Mondays 8AM"),
                // targets ai.automation.trigger, not a business model: see BaseAutomation.default_get
                onClick: () => this.openAutomationForm("on_schedule"),
            },
            {
                image: "/ai_agentic/static/src/img/ai_trigger_on_date.svg",
                title: _t("Based on a Date Field"),
                description: _t("Run once per record, when a specific date is reached"),
                onClick: () => this.openAutomationForm("on_time"),
            },
            {
                image: "/ai_agentic/static/src/img/ai_trigger_create.svg",
                title: _t("After Creation"),
                description: _t("Run whenever a new record is added"),
                onClick: () => this.openAutomationForm("on_time_created"),
            },
            {
                image: "/ai_agentic/static/src/img/ai_trigger_update.svg",
                title: _t("After Update"),
                description: _t("Run whenever a specific field gets updated"),
                onClick: () => this.openAutomationForm("on_time_updated"),
            },
        ];
    }

    openAutomationForm(trigger) {
        this.openTriggerForm("base.automation", { ai_preset_trigger: trigger });
    }

    openTriggerForm(resModel, context) {
        this.props.close();
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            views: [[false, "form"]],
            context: { default_ai_agent_id: this.props.agentId, ...context },
        });
    }

    async onClickHelp() {
        const thread = this.store.discuss.thread;
        this.dialog.closeAll();
        thread.open({ focus: true, fromMessagingMenu: true, bypassCompact: true });
        await thread.post(HELP_PROMPT.toString());
    }
}
