import { Component, markRaw, t, useProps } from "@odoo/owl";
import { CommandPalette, defaultCommandItemProps } from "@web/core/commands/command_palette";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { highlightText } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";

const commandProviderRegistry = registry.category("command_provider");

class AskAICommand extends Component {
    static template = "ai.AskAICommand";
    props = useProps({
        imgUrl: t.string(),
        ...defaultCommandItemProps,
    });
}

async function askAIProvide(aiChatLauncher, options) {
    return [
        {
            action: async () => {
                await aiChatLauncher.launchAIChat({
                    interfaceKey: "systray_ai_button", // own key?
                    userMessage: options.searchValue,
                });
            },
            category: "app",
            Component: AskAICommand,
            props: { imgUrl: "/ai/static/description/icon.png" },
            name: _t("Ask AI"),
        },
    ];
}

commandProviderRegistry.add("ask_ai", {
    namespace: "/",
    provide(options) {
        const aiChatLauncher = useService("aiChatLauncher");
        return askAIProvide(aiChatLauncher, options);
    },
});

// TODO: Add a unit test for this. The Ask AI command should be available in the default
// namespace (CTRL+K) when no commands are found.
patch(CommandPalette.prototype, {
    setup() {
        super.setup();
        this.aiChatLauncher = useService("aiChatLauncher");
    },
    async setCommands(namespace, options = {}) {
        const [askAICommand] = await askAIProvide(this.aiChatLauncher, options);
        const result = await super.setCommands(namespace, options);
        if (
            askAICommand &&
            namespace === "default" &&
            this.state.commands.length === 0 &&
            options.searchValue
        ) {
            this.state.commands = markRaw([
                {
                    ...askAICommand,
                    keyId: this.keyId++,
                    text: highlightText(
                        options.searchValue,
                        askAICommand.name,
                        "fw-bolder text-primary"
                    ),
                },
            ]);
            this.selectCommand(this.state.commands.length ? 0 : -1);
        }
        return result;
    },
});
