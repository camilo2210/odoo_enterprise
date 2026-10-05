import { Plugin } from "@html_editor/plugin";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";
import { getModelName } from "@website/builder/plugins/form/utils";
import { aiChannelBus } from "@ai/utils/ai_channel_bus";
import { getData, triggers } from "@ai/utils/bus_data_getter";
import { getCSSVariableValue, getHtmlStyle } from "@html_editor/utils/formatting";
import { setBuilderCSSVariables } from "@html_builder/utils/utils_css";
import { EDITOR_COLOR_CSS_VARIABLES } from "@html_editor/utils/color";
import {
    AI_EDITABLE_ZONE_SELECTORS,
    AI_WEBSITE_TYPING_TIMEOUT,
    isAiWebsiteBuilderChannel,
    isPageAiEditable,
    pollForData,
} from "@ai_website/utils";
import { aiClientToolsRegistry } from "@ai/discuss/core/common/ai_client_tool_registry";
import { getAiResponsePromise } from "@ai_website/ai_processing_state";

triggers.add("aiWebsitePage");

const CSS_RELOAD_MAX_WAIT = 4000;
const EDITOR_RELOAD_MAX_WAIT = 30000;
const SCRAPER_RECOVERY_DELAY = 5000;

const ANIMATION_RUNTIME_CLASSES = [
    "o_visible",
    "o_animated",
    "o_animating",
    "o_animate_preview",
    "o_animate_in_dropdown",
];
const ANIMATION_RUNTIME_STYLE_PROPS = ["visibility", "animation-play-state", "animation-name"];

/**
 * AI Website Builder Plugin — integrates AI generation with the website builder.
 */
export class AiWebsiteBuilderPlugin extends Plugin {
    static id = "aiWebsiteBuilder";
    static dependencies = [
        "aiScript",
        "customizeWebsite",
        "externalImageSave",
        "history",
        "operation",
        "position",
        "sanitize",
        "savePlugin",
        "websiteFormOption",
    ];

    static shared = ["registerClientToolWithMutex"];

    aiTools = [];

    resources = {
        on_editor_started_handlers: () => {
            this.scraperRecoveryStarted = true;
            this.recoverScraperResults();
        },
    };

    setup() {
        const bus = this.services.bus_service;
        this.scraperResumes = new Set();
        this.scraperResumeAttempts = new Set();
        // CSS reloads are still bus-driven: they are also fired by the
        // server-side refinement pass, outside of any tool call.
        // Keep the bound handler so it can be unsubscribed on destroy: the bus
        // service outlives the plugin and a stale handler would otherwise run
        // on a destroyed editor (e.g. after a menu edit reloads it).
        this.busHandlers = {
            "ai_website/reload_css_bundles": () => this.reloadCssBundles(),
            "ai_website/scraper_result_ready": this.resumeAfterScraping.bind(this),
        };
        for (const [eventName, handler] of Object.entries(this.busHandlers)) {
            bus.subscribe(eventName, handler);
        }
        // Skip when a recovery is already scheduled
        this.onBusConnected = () => {
            if (!this.scraperRecoveryTimer) {
                this.recoverScraperResults();
            }
        };
        for (const event of ["BUS:CONNECT", "BUS:RECONNECT"]) {
            bus.addEventListener(event, this.onBusConnected);
        }
        bus.start();
        this.registerClientToolWithMutex("website_apply_html", (params) =>
            this.applyActions(params)
        );
        this.registerClientToolWithMutex("website_reload_editor", (params) =>
            this.reloadEditor(params)
        );
        this.registerClientToolWithMutex("website_set_form_action", (params) =>
            this.setFormAction(params)
        );
        // `useDataGetter` is an Owl hook and a plugin is not a component.
        this.onFinalizeRequest = () =>
            aiChannelBus.trigger("aiWebsitePage!", {
                finalizePage: this.finalizePage.bind(this),
            });
        aiChannelBus.addEventListener("aiWebsitePage?", this.onFinalizeRequest);
        this.onPageContextRequest = () => {
            if (!this.isDestroyed) {
                aiChannelBus.trigger("view!", { website_page: this.getPageAiContext() });
            }
        };
        aiChannelBus.addEventListener("view?", this.onPageContextRequest);
        aiChannelBus.trigger("aiWebsiteEditorStarted");
        this.toggleAiChatWindows(true);

        this.registerClientToolWithMutex("ai_website_navigate_to_edit", (params) =>
            this.navigateToEditClientTool(params)
        );

        // If the iframe navigated to a new page while the agent was still
        // working (e.g. after create_page), the previous loading screen
        // was destroyed with the old iframe document.
        // Re-apply the same block used for a normal AI turn so the new page
        // stays locked until the agent finishes (or the safety timeout hits).
        const aiResponsePromise = getAiResponsePromise();
        if (aiResponsePromise) {
            (async () => {
                const builder = await pollForData("htmlBuilder");
                if (!builder) {
                    return;
                }
                const unblockBuilderUI = builder.blockBuilderUI();
                const timeoutId = browser.setTimeout(
                    () => unblockBuilderUI(),
                    AI_WEBSITE_TYPING_TIMEOUT
                );
                aiResponsePromise.finally(() => {
                    browser.clearTimeout(timeoutId);
                    unblockBuilderUI();
                });
            })();
        }
    }

    destroy() {
        browser.clearTimeout(this.scraperRecoveryTimer);
        for (const event of ["BUS:CONNECT", "BUS:RECONNECT"]) {
            this.services.bus_service.removeEventListener(event, this.onBusConnected);
        }
        for (const [eventName, handler] of Object.entries(this.busHandlers)) {
            this.services.bus_service.unsubscribe(eventName, handler);
        }
        // If the editor is reloading because of a tool (e.g., menu edit), the
        // user is still in the AI chat: keep it open for the new instance.
        // The tool triggering the reload should take care of cleaning the
        // registry by removing the client tools bound to the instance of
        // `AiWebsiteBuilderPlugin` that is about to be destroyed. This can't
        // be done in `destroy`, as it may run after the new instance's `setup`
        if (!this.isReloadingEditor) {
            this.removeWebsiteBuilderClientToolsFromRegistry();
            this.toggleAiChatWindows(false);
        }
        aiChannelBus.removeEventListener("aiWebsitePage?", this.onFinalizeRequest);
        aiChannelBus.removeEventListener("view?", this.onPageContextRequest);
        super.destroy();
    }

    /**
     * Reload the CSS bundles and wait for the new stylesheet.
     *
     * `reloadBundles` is debounced, and a debounced call that gets superseded never
     * resolves — so cap the wait rather than hang the build on it. Never rejects:
     * a stale palette is worth shipping, losing the whole page is not.
     */
    reloadCssBundles() {
        let timeoutId;

        const timeoutPromise = new Promise((resolve) => {
            timeoutId = setTimeout(() => {
                console.warn(`ai_website: CSS reload not confirmed after ${CSS_RELOAD_MAX_WAIT}ms`);
                resolve();
            }, CSS_RELOAD_MAX_WAIT);
        });

        const reloadPromise = this.dependencies.customizeWebsite
            .reloadBundles()
            .then(() => {
                if (!this.isDestroyed) {
                    // AI updates CSS outside the builder; refresh previews.
                    setBuilderCSSVariables(getHtmlStyle(this.document));
                    this.trigger("on_dom_updated_handlers");
                }
            })
            .catch((error) => {
                console.warn("ai_website: CSS reload failed", error);
            });

        return Promise.race([reloadPromise, timeoutPromise]).finally(() => {
            clearTimeout(timeoutId);
        });
    }

    /**
     * Finalize a full-page build composed by the AI (images, shapes, CSS polish),
     * then apply the result. Called from the `finalize_website_page` client tool.
     *
     * @param {string} html
     * @param {Array} [otherActions] zone-scoped edits bundled in the same tool call
     *   (e.g. a footer edit); applied together with the finalized page rather than
     *   as a separate tool call, so they land deterministically instead of racing it.
     * @param {Object} [targetPage] identity of the page the AI composed
     */
    async finalizePage(html, otherActions = [], targetPage) {
        // The brand kit's palette must be live in the page before it is read off it,
        // or every shape gets painted the previous colours.
        await this.reloadCssBundles();
        let hasFailedStep = false;
        try {
            // Only the palette and the page path are used server-side.
            const page = (await getData("view"))?.website_page;
            let step = "images";
            while (step) {
                const result = await rpc("/ai_website/finalize_page", {
                    html,
                    step,
                    current_view_info: page && {
                        website_page: {
                            website_id: page.website_id,
                            location: page.location,
                            css_variables: page.css_variables,
                        },
                    },
                });
                html = result.html;
                hasFailedStep ||= Boolean(result.error);
                step = result.next_step;
            }
        } catch (e) {
            this.services.notification.add(
                _t("The page could not be finalized. Please try again."),
                { type: "danger" }
            );
            console.error(e);
            throw e;
        }
        const report = this.applyActions({
            actions: [
                { zone: "main", mode: "replace", selector: "", content: html },
                ...otherActions,
            ],
            target_page: targetPage,
        });
        // Pick up the SCSS the CSS pass wrote while the page was being finalized.
        await this.reloadCssBundles();
        if (hasFailedStep) {
            this.services.notification.add(
                _t("The page was built but could not be fully finished."),
                { type: "warning" }
            );
        }
        return report;
    }

    removeWebsiteBuilderClientToolsFromRegistry() {
        this.aiTools.forEach((name) => aiClientToolsRegistry.remove(name));
    }

    /**
     * Add an entry in the client tool registry. The tool call is wrapped
     * into operation.next() to be executed in the builder mutex.
     *
     * @param {String} name - name of the registry entry
     * @param {Function} callback - tool function
     */
    registerClientToolWithMutex(name, callback) {
        this.aiTools.push(name);
        aiClientToolsRegistry.add(
            name,
            async (_, params) => {
                let ran = false;
                let result;
                await this.dependencies.operation.next(async () => {
                    ran = true;
                    result = await callback(params);
                });
                if (!ran) {
                    throw new Error(
                        "The builder discarded this operation (a previous " +
                            "operation timed out); the page was NOT modified."
                    );
                }
                return result;
            },
            { force: true }
        );
    }

    async navigateToEditClientTool(params) {
        await this.onNavigateToEdit(params);
        // goToWebsite()'s own promise resolves as soon as the outer action
        // component mounts, well before the destination page's WebsiteBuilder
        // component (and its `view?` data-getter listener, which current_view_info
        // depends on) is actually ready. Rather than guess at how long that takes,
        // poll the actual thing we need until it succeeds.
        await pollForData("view");
        return params.success_message;
    }

    onNavigateToEdit({ url, save }) {
        return (async () => {
            if (save) {
                // Finish staging the user's latest DOM changes before saving.
                // Save through this editor instance and await its RPC before
                // replacing it with the editor for the new page.
                this.dependencies.history.commit();
                await this.dependencies.savePlugin.save();
            } else {
                this.dependencies.history.reset();
            }
            await this.services.website.goToWebsite({ path: url, edition: true });
        })();
    }

    toggleAiChatWindows(unfold) {
        const mailStore = this.services["mail.store"];
        if (!mailStore?.chatHub) {
            return;
        }
        [...mailStore.chatHub[unfold ? "folded" : "opened"]]
            .filter((w) => isAiWebsiteBuilderChannel(w.channel))
            .forEach((w) => (unfold ? w.open() : w.fold()));
    }

    scheduleScraperRecovery() {
        if (!this.isDestroyed && !this.scraperRecoveryTimer) {
            this.scraperRecoveryTimer = browser.setTimeout(() => {
                this.scraperRecoveryTimer = undefined;
                this.recoverScraperResults();
            }, SCRAPER_RECOVERY_DELAY);
        }
    }

    async recoverScraperResults() {
        const website = this.services.website;
        const page = website?.currentWebsite;
        if (
            this.isDestroyed ||
            !this.scraperRecoveryStarted ||
            this.recoveringScraperResults ||
            !website?.isDesigner ||
            page?.metadata?.translatable ||
            page?.metadata?.mainObject?.model !== "website.page"
        ) {
            return;
        }
        this.recoveringScraperResults = true;
        try {
            const results = await rpc("/ai_website/ready_scraper_results", {
                website_id: page.id,
                main_object: page.metadata.mainObject,
            });
            // Coalesce duplicate bus events until the server has been checked
            // again, while allowing an unconsumed result to be retried.
            for (const key of this.scraperResumeAttempts) {
                if (!this.scraperResumes.has(key)) {
                    this.scraperResumeAttempts.delete(key);
                }
            }
            for (const result of results) {
                await this.resumeAfterScraping(result);
            }
        } catch (error) {
            console.warn("ai_website: could not recover scraping results", error);
            this.scheduleScraperRecovery();
        } finally {
            this.recoveringScraperResults = false;
        }
    }

    async resumeAfterScraping({
        channel_id: channelId,
        session_id: sessionId,
        resume_token: resumeToken,
        target_page: targetPage,
        tool_call_id: callId,
    }) {
        if (this.isDestroyed || !this.isEditingTargetPage(targetPage)) {
            return;
        }
        const resumeKey = `${channelId}:${callId}`;
        if (this.scraperResumeAttempts.has(resumeKey)) {
            return;
        }
        this.scraperResumes.add(resumeKey);
        this.scraperResumeAttempts.add(resumeKey);
        try {
            const channel = await this.services["mail.store"]["discuss.channel"].getOrFetch(channelId);
            if (
                this.isDestroyed ||
                !isAiWebsiteBuilderChannel(channel) ||
                !this.isEditingTargetPage(targetPage)
            ) {
                return;
            }
            await channel.thread.requestAiSessionAdvance("/ai/resume_pending_interaction", {
                session_id: sessionId,
                resume_token: resumeToken,
                response: { kind: "async", call_id: callId },
            });
        } catch (error) {
            console.warn("ai_website: could not resume after scraping", error);
        } finally {
            // A completed HTTP request may have declined a busy session lock.
            // Only the server knows whether the result was consumed: check again
            // after a delay, then stop once no ready call remains.
            this.scraperResumes.delete(resumeKey);
            this.scheduleScraperRecovery();
        }
    }

    /**
     * Whether the page open in the builder is the one the AI made its edits for.
     * It prevents from applying the changes if the user moved off the original page.
     *
     * @param {{ main_object: { model: string, id: number }, location: string }} [targetPage]
     */
    isEditingTargetPage(targetPage) {
        const targetObject = targetPage?.main_object;
        if (!targetObject?.model) {
            // The sender did not say which page it edited: nothing to check against.
            return true;
        }
        const currentObject = this.services.website?.currentWebsite?.metadata?.mainObject;
        return (
            currentObject?.model === targetObject.model &&
            currentObject?.id === targetObject.id &&
            (targetPage.website_id === undefined ||
                targetPage.website_id === this.services.website?.currentWebsite?.id)
        );
    }

    /**
     * Try to apply AI-generated changes to the page and report the result.
     *
     * @param {{
     *   actions: [{
     *     mode: string,
     *     zone: string,
     *     selector: string,
     *     content: string,
     *   }],
     *   target_page: { main_object: { model: string, id: number }, location: string },
     * }} payload
     * @returns {Object[]} the apply report
     */
    applyActions({ actions, target_page: targetPage }) {
        if (this.isDestroyed) {
            throw new Error(
                "The editor was closed or reloaded before these changes could " +
                    "be applied; the page was NOT modified."
            );
        }
        if (!this.isEditingTargetPage(targetPage)) {
            this.services.notification.add(
                _t(
                    "The AI finished changes meant for %s, which is no longer the page being edited. They were not applied.",
                    targetPage.location || _t("another page")
                ),
                { type: "warning" }
            );
            throw new Error("The page being edited has changed; the changes were NOT applied.");
        }
        const edits = [];
        const results = [];
        for (const { zone, mode, selector, content } of actions) {
            const result = {
                description: `${mode}${selector ? ` on "${selector}"` : ""} in ${zone}`,
            };
            results.push(result);
            const zoneEl = this.editable.querySelector(AI_EDITABLE_ZONE_SELECTORS[zone]);
            if (!zoneEl) {
                result.error = `Zone element not found for zone: ${zone}`;
                continue;
            }
            zoneEl.dataset.containsAiContent = "true";
            // Queued changes can be applied before the save plugin starts
            // observing mutations on a newly redirected page. Mark its
            // enclosing view dirty explicitly so Save persists the AI edit.
            zoneEl.closest(".o_savable")?.classList.add("o_dirty");
            // sanitized during parsing - we can't trust LLM output
            const { sanitizedContent, wasSanitized } = this.parseAndSanitizeHtml(content);
            if (wasSanitized) {
                if (!sanitizedContent.hasChildNodes()) {
                    result.error = "Everything was dropped by the sanitizer";
                    continue;
                }
                result.sanitizer_note =
                    "The editor removed unsafe or unsupported markup from your HTML. " +
                    "`sanitized_html` is what is actually on the page: compare it with " +
                    "what you sent, and tell the user what is missing.";
                // Read before insertion: appending the fragment empties it.
                result.sanitized_html = [...sanitizedContent.childNodes]
                    .map((node) => node.outerHTML ?? node.textContent)
                    .join("");
            }
            if (!selector) {
                // If we have sections wrapped in some container, we should
                // unwrap it.
                if (
                    sanitizedContent.children.length === 1 &&
                    sanitizedContent.firstElementChild.querySelectorAll(":scope > section").length >
                        1
                ) {
                    sanitizedContent.replaceChildren(
                        ...sanitizedContent.firstElementChild.children
                    );
                }
                this.dependencies.aiScript.stopScripts(zoneEl);
                this.markAiContent(sanitizedContent);
                zoneEl.replaceChildren(sanitizedContent);
                this.dependencies.aiScript.restartScripts(zoneEl);
                continue;
            }
            let targetEls;
            try {
                targetEls = zoneEl.querySelectorAll(selector);
            } catch (err) {
                if (err.name === "SyntaxError") {
                    // Catches only errors from non-string or malformed selectors. The check for err.name is
                    // required as some browser may throw another type of error such as DOMException.
                    result.error = `Invalid CSS selector: ${selector}`;
                    continue;
                }
                throw err;
            }
            if (!targetEls.length) {
                result.error = `Nothing matches ${selector}`;
                continue;
            }
            this.markAiContent(sanitizedContent);
            const methods = {
                after: (el) => {
                    el.after(sanitizedContent.cloneNode(true));
                    this.dependencies.aiScript.restartScripts(el.nextElementSibling);
                },
                before: (el) => {
                    el.before(sanitizedContent.cloneNode(true));
                    this.dependencies.aiScript.restartScripts(el.previousElementSibling);
                },
                replace: (el) => {
                    this.dependencies.aiScript.stopScripts(el);
                    const cloneEl = sanitizedContent.cloneNode(true);
                    const newEl = cloneEl.firstElementChild;
                    el.replaceWith(cloneEl);
                    if (sanitizedContent.childElementCount === 1) {
                        this.trigger("on_ai_website_element_replaced_handlers", el, newEl);
                    }
                    if (newEl) {
                        this.dependencies.aiScript.restartScripts(newEl);
                    }
                },
            };
            edits.push(() => targetEls.forEach(methods[mode]));
        }

        // Execute all the edits at the end so the selectors are done on the
        // original DOM and not affected by previous edits.
        // This may happen with selectors such as :nth-child().
        edits.forEach((edit) => edit());
        this.dependencies.history.commit();
        return results;
    }

    markAiContent(rootEl) {
        for (const el of rootEl.children) {
            el.dataset.containsAiContent = "true";
        }
    }

    /**
     * Wire a form to an action exactly like the editor's action switch
     * (`SelectAction`), and/or set hidden destination fields like the
     * sidebar's action fields do (`AddActionFieldAction`), then report the
     * resulting form and the action's destination fields (with candidate
     * records) so the agent can let the user choose the destinations.
     *
     * @param {Object} params
     * @param {String} params.selector CSS selector of the form or its section
     * @param {String} params.action_key `website_form_key` of the target action
     * @param {Array<{name: String, value: String}>} params.fields hidden
     *        destination/preset values to set
     * @returns {Object} The result payload for the AI agent. Includes `error`
     *        on failure. On success, includes `form_html`, `destination_fields`
     *        and optionally `previous_form_html`, `note`, and an array of
     *        `field_errors`.
     */
    async setFormAction({ selector, action_key, fields }) {
        const targetEl = this.editable.querySelector(selector);
        const formEl = targetEl?.closest("form") || targetEl?.querySelector("form");
        if (!formEl || !formEl.closest(".s_website_form")) {
            return {
                error:
                    `No website form matches "${selector}". The form must keep its ` +
                    "s_website_form section structure; re-apply the form snippet if it was lost.",
            };
        }
        const formOptionPlugin = this.dependencies.websiteFormOption;
        const models = await formOptionPlugin.fetchModels(formEl);
        const targetForm = models.find((m) => (m.website_form_key || m.model) === action_key);
        if (!targetForm) {
            return {
                error:
                    `Unknown form action "${action_key}". Available actions: ` +
                    `${models.map((m) => m.website_form_key || m.model).join(", ")}.`,
            };
        }
        const result = { field_errors: [] };
        const formInfo = await formOptionPlugin.prepareFormModel(formEl, targetForm);
        if (formEl.dataset.model_name !== targetForm.model) {
            if (formEl.getAttribute("hide-change-model")) {
                return {
                    error: "This form's action cannot be changed (the form is managed by its page).",
                };
            }
            const activeForm = models.find((m) => m.model === getModelName(formEl)) || targetForm;
            result.previous_form_html = formEl.outerHTML;
            await formOptionPlugin.applyFormModel(formEl, activeForm, targetForm.id, formInfo);
        }
        const authorizedFields = await formOptionPlugin.fetchAuthorizedFields(formEl);
        for (const { name, value } of fields || []) {
            const fieldDef = authorizedFields[name];
            if (!fieldDef || fieldDef._property) {
                result.field_errors.push(
                    `"${name}" is not a field of ${targetForm.model}; not set.`
                );
                continue;
            }
            let fieldValue = value;
            if (["many2one", "integer"].includes(fieldDef.type)) {
                fieldValue = parseInt(value);
                if (isNaN(fieldValue)) {
                    result.field_errors.push(
                        `"${name}" takes the numeric id of the targeted record, not "${value}"; not set.`
                    );
                    continue;
                }
            }
            formOptionPlugin.addHiddenField(formEl, fieldValue, name);
        }
        this.dependencies.history.commit();
        if (!result.field_errors.length) {
            delete result.field_errors;
        }
        result.form_html = formEl.outerHTML;
        result.destination_fields = (formInfo.fields || []).map((field) => ({
            name: field.name,
            label: field.string,
            required: !!field.required,
            prefilled_value:
                formEl.querySelector(`.s_website_form_dnone input[name="${field.name}"]`)?.value ||
                "",
            candidates: (field.records || [])
                .slice(0, 20)
                .map(({ id, display_name }) => ({ id, display_name })),
        }));
        if (result.destination_fields.length) {
            result.note =
                "Every destination field above must be confirmed by the user before the " +
                "form is done, a prefilled_value is a default, NOT a user choice.";
        }
        return result;
    }

    /**
     * Save the pending page edit and reload the editor. Used to render
     * changes that require a reload such as changes to website menu.
     */
    async reloadEditor(returnMessage) {
        if (this.isReloadingEditor) {
            // A reload is already on the way.
            throw new Error(
                "A reload of the editor is already in progress; this call did " +
                    "nothing. Ask for the current page state before editing further."
            );
        }
        this.isReloadingEditor = true;
        this.removeWebsiteBuilderClientToolsFromRegistry();
        aiChannelBus.removeEventListener("view?", this.onPageContextRequest);
        const nextEditorStarted = Promise.race([
            new Promise((resolve) =>
                aiChannelBus.addEventListener("aiWebsiteEditorStarted", () => resolve(true), {
                    once: true,
                })
            ),
            new Promise((resolve) => setTimeout(() => resolve(false), EDITOR_RELOAD_MAX_WAIT)),
        ]);
        try {
            await this.dependencies.savePlugin.save();
            await this.config.reloadEditor();
        } catch (e) {
            this.isReloadingEditor = false;
            throw e;
        }
        if (!(await nextEditorStarted)) {
            console.warn(`AI Website: editor hasn't reloaded after ${EDITOR_RELOAD_MAX_WAIT} ms`);
        }
        return returnMessage;
    }

    getPageAiContext() {
        // Mutations from a recent user edit may still be staged when the chat
        // request is sent. Commit them before reporting pending_changes so the
        // agent can ask whether to save or discard them.
        this.dependencies.history.commit();

        const websiteService = this.services.website;
        const metadata = websiteService.currentWebsite.metadata;
        // Collect context before cloning: extensions may update the editable DOM.
        const extraContext = Object.assign(
            {},
            ...this.trigger("on_ai_website_page_context_handlers")
        );

        const getZoneContent = (zoneSelector) => {
            const el = this.editable.querySelector(zoneSelector);
            if (!el) {
                return "";
            }
            const clone = el.cloneNode(true);
            for (const animatedEl of clone.querySelectorAll(".o_animate, .o_animate_preview")) {
                animatedEl.classList.remove(...ANIMATION_RUNTIME_CLASSES);
                for (const prop of ANIMATION_RUNTIME_STYLE_PROPS) {
                    animatedEl.style.removeProperty(prop);
                }
                if (!animatedEl.getAttribute("style")) {
                    animatedEl.removeAttribute("style");
                }
            }
            return clone.innerHTML;
        };

        const getOdooCssVariables = () => {
            const htmlStyle = getHtmlStyle(this.document);
            const cssVarValues = {};
            for (const varName of EDITOR_COLOR_CSS_VARIABLES.filter(
                (v) => v.startsWith("o-cc") || v.startsWith("o-color-")
            )) {
                cssVarValues[varName] = getCSSVariableValue(varName, htmlStyle);
            }
            return cssVarValues;
        };

        const pageContext = {
            website_id: websiteService.currentWebsite?.id,
            title: metadata.title,
            lang: metadata.lang,
            direction: metadata.direction,
            location: websiteService.currentLocation,
            main_object: metadata.mainObject,
            is_page_ai_editable: isPageAiEditable(websiteService),
            editable_zones: {
                main: getZoneContent(AI_EDITABLE_ZONE_SELECTORS.main),
                footer: getZoneContent(AI_EDITABLE_ZONE_SELECTORS.footer),
            },
            css_variables: getOdooCssVariables(),
            pending_changes: this.dependencies.history.canUndo(),
        };
        return Object.assign(pageContext, extraContext);
    }

    /**
     * Sanitize HTML via DOMPurify (SanitizePlugin) before adding it to the
     * page. Returns the sanitized content, and whether anything was dropped
     * from what was given.
     *
     * @param {string} html - the HTML content to sanitize
     * @returns {{
     *  sanitizedContent: DocumentFragment,
     *  wasSanitized: boolean
     * }}
     */
    parseAndSanitizeHtml(html) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(`<div>${html}</div>`, "text/html");
        const fragment = this.document.createDocumentFragment();
        let wasSanitized = false;
        for (const child of [...doc.body.firstChild.childNodes]) {
            const imported = this.document.importNode(child, true);
            if (imported.nodeType === Node.ELEMENT_NODE) {
                try {
                    this.dependencies.aiScript.normalizeScripts(imported);
                    // DOMPurify's DOM-clobbering guard strips `name` attributes
                    // whose value collides with a form property (e.g. the
                    // crm.lead/project.task required field literally named
                    // "name"), silently unbinding the field. The stock editor
                    // ships those very attributes, so restore the ones that
                    // were explicitly present on form inputs.
                    const namedInputEls = [
                        ...imported.querySelectorAll(".s_website_form_input[name]"),
                    ];
                    const savedNames = namedInputEls.map((el) => [el, el.getAttribute("name")]);
                    // Re-set them before the snapshot: `setAttribute` appends,
                    // so putting a name back below would otherwise move it in
                    // the serialization and read as a sanitization.
                    for (const [el, name] of savedNames) {
                        el.removeAttribute("name");
                        el.setAttribute("name", name);
                    }
                    const beforeSanitize = imported.outerHTML;
                    const restoreScripts = this.dependencies.aiScript.detachScripts(imported);
                    this.dependencies.sanitize.sanitize(imported);
                    restoreScripts();
                    for (const [el, name] of savedNames) {
                        if (!el.getAttribute("name") && imported.contains(el)) {
                            el.setAttribute("name", name);
                        }
                    }
                    wasSanitized ||= imported.outerHTML !== beforeSanitize;
                    this.trigger("on_ai_website_html_imported_handlers", imported);
                    fragment.appendChild(imported);
                } catch (e) {
                    if (e instanceof TypeError) {
                        wasSanitized = true;
                        continue;
                    }
                    throw e;
                }
            } else if (imported.nodeType === Node.TEXT_NODE) {
                fragment.appendChild(imported);
            } else {
                // All other node types may potentially be unsafe and are
                // dropped (comments, PIs, CDATA, ...)
                wasSanitized = true;
            }
        }
        // The agent works from images it found on other sites, so it hands us URLs
        // pointing at those sites. Flag them here rather than asking the agent to call a
        // tool for it: they are then downloaded into Odoo when the user saves the page.
        this.dependencies.externalImageSave.markExternalImages(fragment);
        return { sanitizedContent: fragment, wasSanitized };
    }
}

registry.category("website-plugins").add(AiWebsiteBuilderPlugin.id, AiWebsiteBuilderPlugin);
