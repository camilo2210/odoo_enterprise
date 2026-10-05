import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

export class AiWebsiteBuilderTranslationPlugin extends Plugin {
    static id = "aiWebsiteBuilderTranslation";
    setup() {
        this.stopAiScripts();
    }

    stopAiScripts(rootEl = this.editable) {
        rootEl.querySelectorAll("script[data-ai-script-id]").forEach((scriptEl) => {
            this.window.__aiScriptsManager__.manager.disposeScript(scriptEl);
        });
    }
}

registry
    .category("translation-plugins")
    .add(AiWebsiteBuilderTranslationPlugin.id, AiWebsiteBuilderTranslationPlugin);
