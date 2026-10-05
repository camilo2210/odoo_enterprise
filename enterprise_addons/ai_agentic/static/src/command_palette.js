import { Component, t, usePlugin, useProps, useScope } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { normalize } from "@web/core/l10n/utils";
import { ORM } from "@web/core/orm_plugin";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { imageUrl } from "@web/core/utils/urls";

const commandProviderRegistry = registry.category("command_provider");
const commandCategoryRegistry = registry.category("command_categories");

commandCategoryRegistry.add("AI_AGENTS", { namespace: "@", name: _t("Agents") }, { sequence: 30 });

export class AICommand extends Component {
    static template = "ai_agentic.AICommand";

    props = useProps({
        executeCommand: t.function(),
        name: t.string(),
        subtitle: t.string(),
        imgUrl: t.string(),
        action: t.object().optional(),
        searchValue: t.string(),
        slots: t.object(),
    });

    setup() {
        super.setup();
        this.ui = useService("ui");
    }
}
export class AICommandPalette {
    constructor(options) {
        this.options = options;
        this.orm = usePlugin(ORM);
        this.ui = useService("ui");
        this.actions = useService("action");
        this.commands = [];
        this.options = options;
        this.cleanedTerm = normalize(this.options.searchValue);
        this.agents = [];
    }

    async fetch() {
        this.agents = await this.orm.searchRead(
            "ai.agent",
            [],
            ["id", "name", "subtitle", "partner_id"],
            { load: false }
        );
    }

    async buildResults(filtered) {
        this.agents
            .filter(
                (agent) =>
                    (normalize(agent.name).includes(this.cleanedTerm) ||
                        (agent.subtitle && normalize(agent.subtitle).includes(this.cleanedTerm))) &&
                    (!filtered || !filtered.has(agent))
            )
            .slice(0, 5)
            .forEach((agent) => {
                this.commands.push({
                    Component: AICommand,
                    action: async () => {
                        const result = await this.orm.call("ai.agent", "open_agent_chat", [
                            agent.id,
                        ]);
                        if (result) {
                            this.actions.doAction(result, { clearBreadcrumbs: true });
                        }
                    },
                    name: agent.name,
                    props: {
                        imgUrl: imageUrl("ai.agent", agent.id, "image_128"),
                        subtitle: agent.subtitle ? agent.subtitle : "",
                    },
                    category: "AI_AGENTS",
                });
            });
    }
}

commandProviderRegistry.add("chat_with_agent", {
    namespace: "@",
    async provide(options) {
        const scope = useScope();
        const palette = scope.run(() => new AICommandPalette(options));
        await palette.fetch();
        palette.buildResults();
        return palette.commands;
    },
});
