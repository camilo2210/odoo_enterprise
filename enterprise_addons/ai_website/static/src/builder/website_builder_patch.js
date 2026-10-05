import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { WebsiteBuilder } from "@website/builder/website_builder";
import { useBus } from "@web/core/utils/hooks";
import { isPageAiEditable } from "../utils";

patch(WebsiteBuilder.prototype, {
    setup() {
        super.setup();
        useBus(this.env.bus, "RELOAD_EDITOR", async (ev) => await this.reloadEditor(ev.detail));
    },
    get isPageAiEditable() {
        return isPageAiEditable(this.websiteService);
    },
    get aiAssistantTooltip() {
        if (!this.isPageAiEditable) {
            return _t("The AI Assistant is not yet available on this page");
        }
        if (!this.websiteService.isDesigner) {
            return _t("The AI Assistant requires 'Editor and Designer' access");
        }
        return _t("AI Assistant");
    },
    get isTranslationMode() {
        return this.websiteService.currentWebsite?.metadata.translatable;
    },
    async onAiChatClick() {
        const launcher = this.env.services["aiChatLauncher"];
        if (!launcher) {
            this.env.services["notification"].add("AI service not available.", { type: "warning" });
            return;
        }
        try {
            await launcher.launchAIChat({
                interfaceKey: "website_builder_ai",
                channelTitle: "AI Website Assistant",
            });
        } catch (e) {
            this.env.services["notification"].add("Failed to open AI chat.", { type: "danger" });
            console.error(e);
        }
    },
    async reloadEditor({ save = true } = {}) {
        if (save) {
            this.editor.shared.history.commit();
            await this.editor.shared.savePlugin.save();
        }
        await this.editor.config.reloadEditor({ target: "main" });
    },
});
