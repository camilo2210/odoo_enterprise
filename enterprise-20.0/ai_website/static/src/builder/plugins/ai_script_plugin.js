import { Plugin } from "@html_editor/plugin";
import { withSequence } from "@html_editor/utils/resource";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { AiGeneratedScriptsPanel } from "../ai_generated_scripts_panel";
import { proxy } from "@odoo/owl";
import { getScriptTitle } from "../../utils";

export class AiScriptPlugin extends Plugin {
    static id = "aiScript";
    static dependencies = ["domObserver", "history"];
    static shared = [
        "detachScripts",
        "removeScript",
        "restartScripts",
        "runScript",
        "normalizeScripts",
        "stopScripts",
        "stopScript",
    ];

    aiGeneratedScriptsPanelProps = proxy({ scripts: [] });

    resources = {
        lower_panel_entries: withSequence(10, {
            Component: AiGeneratedScriptsPanel,
            props: this.aiGeneratedScriptsPanelProps,
        }),
        on_normalized_handlers: this.updateAiGeneratedScriptsPanelProps.bind(this),
        on_ai_script_update_handlers: this.updateAiGeneratedScriptsPanelProps.bind(this),
        system_attributes: ["data-ai-script-stopped", "data-ai-tracked", "data-ai-temp"],
        on_will_save_handlers: (rootEl) => {
            this.stopScripts(rootEl);
            this.cleanAiMutations(rootEl);
        },
        on_saved_handlers: this.restartScripts.bind(this),
        on_snippet_dropped_handlers: ({ snippetEl }) => this.restartScripts(snippetEl),
    };

    setup() {
        this.aiScriptsManager = this.window.__aiScriptsManager__?.manager;
        this.domObserver = this.dependencies.domObserver;
        if (this.aiScriptsManager) {
            this.aiScriptsManager.runCallback = (fn, args, { scriptEl }) => {
                try {
                    return this.domObserver.ignore(() => fn(...args));
                } catch (error) {
                    console.warn("AI script failed:", error);
                    this.stopScript(scriptEl);
                    this.services.notification.add(
                        _t(
                            'Script "%s" got an error and has been paused. Please, prompt AI again to fix it.',
                            getScriptTitle(scriptEl)
                        ),
                        {
                            type: "danger",
                        }
                    );
                }
            };
        }
        this.restartScripts(this.editable);
        this.updateAiGeneratedScriptsPanelProps();
    }

    destroy() {
        this.aiScriptsManager?.disposeAll();
        super.destroy();
    }

    updateAiGeneratedScriptsPanelProps() {
        const scriptEls = [...this.editable.querySelectorAll("script[data-ai-script-id]")];
        this.aiGeneratedScriptsPanelProps.scripts = scriptEls.map((el) => ({
            el,
            isStopped: el.dataset.aiScriptStopped,
        }));
    }

    insertScript(parentEl, scriptId, scriptContent) {
        const scriptEl = this.document.createElement("script");
        scriptEl.dataset.aiScriptId = scriptId;
        scriptEl.textContent = scriptContent;
        const protectedInsert = this.aiScriptsManager.protectMutations(() => {
            const existingScriptEl = parentEl.querySelector(
                `script[data-ai-script-id="${scriptId}"]`
            );
            if (existingScriptEl) {
                this.aiScriptsManager.disposeScript(existingScriptEl);
                existingScriptEl.remove();
            }
            parentEl.appendChild(scriptEl);
        });
        protectedInsert();
        return scriptEl;
    }

    removeScript(el) {
        const parentEl = el.parentElement;
        if (!parentEl) {
            return;
        }
        const scriptId = el.dataset.aiScriptId;
        const scriptContent = el.textContent;
        let currentScriptEl = el;

        const removeCurrentScript = () => {
            this.aiScriptsManager.disposeScript(currentScriptEl);
            currentScriptEl.remove();
        };
        this.domObserver.stageCustomMutation({
            apply: () => removeCurrentScript(),
            revert: () => {
                currentScriptEl = this.insertScript(parentEl, scriptId, scriptContent);
            },
        });
        removeCurrentScript();
    }

    stopScripts(rootEl = this.editable) {
        const scriptEls = rootEl.querySelectorAll("script[data-ai-script-id]");
        for (const scriptEl of scriptEls) {
            this.stopScript(scriptEl);
        }
    }

    stopScript(scriptEl) {
        this.domObserver.ignore(() => this.aiScriptsManager.disposeScript(scriptEl));
        scriptEl.setAttribute("data-ai-script-stopped", "1");
        this.trigger("on_ai_script_update_handlers");
    }

    runScript(scriptEl) {
        if (!scriptEl.dataset.aiScriptStopped) {
            return;
        }
        const parentEl = scriptEl.parentElement;
        this.domObserver.ignore(() =>
            this.insertScript(parentEl, scriptEl.dataset.aiScriptId, scriptEl.textContent)
        );
        this.trigger("on_ai_script_update_handlers");
    }

    restartScripts(rootEl = this.editable) {
        this.cleanAiMutations(rootEl);
        if (rootEl.matches("script[data-ai-script-id]")) {
            this.insertScript(rootEl.parentNode, rootEl.dataset.aiScriptId, rootEl.textContent);
            return;
        }
        const scriptEls = rootEl.querySelectorAll("script[data-ai-script-id]");
        for (const scriptEl of scriptEls) {
            // This "restarts" the scripts.
            this.insertScript(
                scriptEl.parentNode,
                scriptEl.dataset.aiScriptId,
                scriptEl.textContent
            );
        }
    }

    cleanAiMutations(rootEl = this.editable) {
        rootEl.querySelectorAll("[data-ai-temp]").forEach((el) => el.remove());
        rootEl.querySelectorAll("[data-ai-tracked]").forEach((el) => {
            this.aiScriptsManager.restoreElement(el);
        });
        rootEl.querySelectorAll("[data-ai-script-stopped]").forEach((el) => {
            delete el.dataset.aiScriptStopped;
        });
    }

    /**
     * Swap the scripts of `el` for placeholders, and return the callback that
     * puts them back once `el` has been sanitized.
     *
     * @param {Element} el
     * @returns {Function} restores the detached scripts
     */
    detachScripts(el) {
        const replaceScript = (scriptEl) => {
            const placeholderEl = this.document.createElement("span");
            if (scriptEl.dataset.aiScriptId) {
                placeholderEl.dataset.aiScriptPlaceholderId = scriptEl.dataset.aiScriptId;
                scriptEl.replaceWith(placeholderEl);
                return placeholderEl;
            }
        };
        // If el itself is a script just swap it for a placeholder.
        if (el.matches("script")) {
            const placeholderEl = replaceScript(el);
            return () => placeholderEl?.replaceWith(el);
        }
        const scriptEls = [...el.querySelectorAll("script")];
        scriptEls.forEach(replaceScript);
        return () => {
            scriptEls.forEach((scriptEl) => {
                if (scriptEl.dataset.aiScriptId) {
                    const placeholderEl = el.querySelector(
                        `[data-ai-script-placeholder-id="${scriptEl.dataset.aiScriptId}"]`
                    );
                    placeholderEl.replaceWith(scriptEl);
                }
            });
        };
    }

    normalizeScripts(el) {
        const scriptEls = el.querySelectorAll("[data-ai-script-id]");
        for (const scriptEl of scriptEls) {
            // We need to make the id unique, to avoid possible collisions.
            if (scriptEl.dataset.aiScriptId.split("--").length === 1) {
                scriptEl.dataset.aiScriptId += `--${this.getScriptUniqueId()}`;
            }
        }
    }

    getScriptUniqueId() {
        return Date.now().toString(36) + Math.random().toString(36).substring(2);
    }
}

registry.category("website-plugins").add(AiScriptPlugin.id, AiScriptPlugin);
