import { aiSessionIdentifier } from "@ai/utils/ai_session_identifier";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { advanceTime, queryAll, queryFirst, waitFor, waitForNone } from "@odoo/hoot-dom";
import {
    setupWebsiteBuilder,
    defineWebsiteModels,
    setupSidebarBuilderForTranslation,
} from "@website/../tests/builder/website_helpers";
import {
    contains,
    patchWithCleanup,
    MockServer,
    mockService,
    onRpc,
    webModels,
    authenticate,
} from "@web/../tests/web_test_helpers";
import { waitUntil } from "@web/core/macro";
import { dragenterFiles, dropFiles, startServer } from "@mail/../tests/mail_test_helpers";
import { defineAIModels } from "@ai/../tests/ai_test_helpers";
import { setupAiWebsiteBuilder } from "./ai_website_test_helpers";
import { aiClientToolsRegistry } from "@ai/discuss/core/common/ai_client_tool_registry";

function defineAiWebsiteModels() {
    defineAIModels();
    defineWebsiteModels({
        // `defineAIModels` already calls `defineMailModels` and overrides one
        // of them (i.e. DiscussChannel).
        includeMailModels: false,
    });
}

defineAiWebsiteModels();

function mockApplyHTML(actions) {
    const applyHTML = aiClientToolsRegistry.get("website_apply_html", null);
    return applyHTML?.(null, { actions });
}

describe("AI Website Builder Plugin", () => {
    test("should fetch requested computed styles for selected elements", async () => {
        await setupWebsiteBuilder(`
            <section data-ai-id="ai-first" style="display: flex; font-size: 21px;"></section>
            <section data-ai-id="ai-second" style="opacity: 0.5;"></section>
        `);

        const result = await aiClientToolsRegistry.get("fetch_website_styles")(null, {
            elements: [
                { id: "ai-first", properties: ["display", "font-size"] },
                { id: "ai-second", properties: ["opacity"] },
                { id: "ai-missing", properties: ["display"] },
            ],
        });

        expect(result).toEqual({
            elements: [
                {
                    id: "ai-first",
                    styles: {
                        display: "flex",
                        "font-size": "21px",
                    },
                },
                { id: "ai-second", styles: { opacity: "0.5" } },
                { id: "ai-missing", error: "Element is no longer available" },
            ],
        });
    });

    test("should apply html actions correctly", async () => {
        await setupWebsiteBuilder("");

        await mockApplyHTML([
            {
                zone: "main",
                mode: "replace",
                content: `<section id="section_1">Section 1</section>`,
            },
        ]);

        expect(":iframe #wrap > #section_1").toHaveCount(1);

        await mockApplyHTML([
            {
                zone: "main",
                mode: "before",
                selector: "section",
                content: `<section id="section_0"></section>`,
            },
            {
                zone: "main",
                mode: "after",
                selector: "section",
                content: `<section id="section_2"></section>`,
            },
        ]);

        expect(":iframe #wrap > section").toHaveCount(3);

        // Check that added sections are in correct order
        const sections = queryAll(":iframe #wrap > section");
        expect(sections[0]).toHaveAttribute("id", "section_0");
        expect(sections[1]).toHaveAttribute("id", "section_1");
        expect(sections[2]).toHaveAttribute("id", "section_2");

        // Remove section_0 and section_1
        await mockApplyHTML([
            {
                zone: "main",
                mode: "replace",
                selector: "section:nth-child(1)",
                content: "",
            },
            {
                zone: "main",
                mode: "replace",
                selector: "section:nth-child(2)",
                content: "",
            },
        ]);

        expect(":iframe #wrap > section").toHaveCount(1);
        expect(":iframe #wrap > section").toHaveAttribute("id", "section_2");
        expect(":iframe #wrap").toHaveAttribute("data-contains-ai-content", "true");
        expect(":iframe #wrap").toHaveClass("o_dirty");
    });

    test("should only apply html actions meant for the page being edited", async () => {
        const notifications = [];
        mockService("notification", {
            add(message) {
                notifications.push(message);
            },
        });
        mockService("website", {
            get currentWebsite() {
                return {
                    metadata: { mainObject: { model: "website.page", id: 1 } },
                    default_lang_id: { code: "en_US" },
                };
            },
        });
        await setupWebsiteBuilder("");

        await aiClientToolsRegistry.get("website_apply_html")(null, {
            actions: [
                {
                    zone: "main",
                    mode: "replace",
                    content: `<section id="edited_page"></section>`,
                },
            ],
            target_page: { main_object: { model: "website.page", id: 1 }, location: "/here" },
        });

        await waitFor(":iframe #wrap > #edited_page");

        // The AI worked asynchronously and the user saved and opened another page
        // meanwhile: these edits are for a page that is no longer on screen.
        await expect(
            aiClientToolsRegistry.get("website_apply_html")(null, {
                actions: [
                    {
                        zone: "main",
                        mode: "replace",
                        content: `<section id="other_page"></section>`,
                    },
                ],
                target_page: { main_object: { model: "website.page", id: 2 }, location: "/about-us" },
            })
        ).rejects.toThrow("The page being edited has changed; the changes were NOT applied.");

        await waitUntil(() => notifications.length);
        expect(notifications[0]).toMatch("/about-us");
        expect(":iframe #other_page").toHaveCount(0);
        expect(":iframe #wrap > #edited_page").toHaveCount(1);
    });

    test("should ignore DOM mutations wrapped in protectMutations", async () => {
        const { getEditor } = await setupAiWebsiteBuilder(`<section><a>Click</a></section>`);

        const editor = getEditor();
        const iframeDoc = queryFirst(":iframe");

        const btn = queryFirst(":iframe a");
        const section = queryFirst(":iframe section");

        const onClick = () => {
            const tempEl = iframeDoc.createElement("div");
            tempEl.className = "test-ai-temp-particle";
            tempEl.setAttribute("data-ai-temp", "true");
            section.appendChild(tempEl);
        };
        const commitsBefore = editor.shared.history.getCommits();
        const lastCommitMutations = commitsBefore.at(-1).data.mutations;
        // The helpers live on the iframe window, like on a real page.
        const ai = iframeDoc.defaultView.__aiScriptsManager__.getApi(null);
        btn.addEventListener("click", ai.protectMutations(onClick));
        await contains(":iframe a").click();

        // Verify the temporary element was added to the DOM
        expect(":iframe section > .test-ai-temp-particle").toHaveCount(1);
        // Verify no history commits or mutations were produced by the click event
        const commitsAfter = editor.shared.history.getCommits();
        expect(commitsAfter.length).toBe(commitsBefore.length);
        expect(commitsAfter.at(-1).data.mutations).toBe(lastCommitMutations);
    });

    test("should restore ai dirty elements and strip temporary elements before entering edit mode, and on save", async () => {
        const { openBuilderSidebar } = await setupAiWebsiteBuilder(
            `<section><img class="target" src="/web/image" style="transform: rotate(0deg);"/></section>`,
            {
                openEditor: false,
            },
        );
        onRpc("ir.ui.view", "save", () => {
            // should clean ai scripts modifications when saving.
            expect(":iframe [data-ai-temp], :iframe [data-ai-tracked]").toHaveCount(0);
            expect(":iframe img.target").toHaveOuterHTML(imgBefore);
            expect.step("save");
            return true;
        });
        const iframeDoc = queryFirst(":iframe");
        const img = queryFirst(":iframe img.target");
        const imgBefore = img.outerHTML;
        const section = queryFirst(":iframe section");

        // The helpers live on the iframe window, like on a real page.
        const ai = iframeDoc.defaultView.__aiScriptsManager__.getApi(null);
        const onClick = () => {
            ai.trackElement(img);
            img.style.transform = "rotate(180deg)";
            const tempNode = iframeDoc.createElement("div");
            tempNode.setAttribute("data-ai-temp", "true");
            tempNode.textContent = "Temporary Particle";
            section.appendChild(tempNode);
        };
        img.addEventListener("click", ai.protectMutations(onClick));

        await contains(":iframe img").click();
        expect(img.style.transform).toBe("rotate(180deg)");
        expect(":iframe [data-ai-temp]").toHaveCount(1);

        await openBuilderSidebar();
        // Should clean ai scripts modifications when entering edit mode.
        expect(":iframe [data-ai-temp], :iframe [data-ai-tracked]").toHaveCount(0);
        expect(":iframe img.target").toHaveOuterHTML(imgBefore);

        await contains(":iframe img").click();
        queryFirst(":iframe #wrap").classList.add("o_dirty");
        await contains(".btn[data-action='save']").click();
        expect.verifySteps(["save"]);
    });

    test("a failing script should be paused", async () => {
        mockService("notification", {
            add(message) {
                expect.step("notification");
                expect(message).toMatch('Script "Broken script" got an error');
            },
        });
        patchWithCleanup(console, {
            warn: () => expect.step("warning"),
        });
        await setupAiWebsiteBuilder(`<section><div class="target">content</div></section>`);

        await mockApplyHTML([
            {
                zone: "main",
                mode: "replace",
                content: `<section class="ai-html">
                    <div class="target">content</div>
                    <button class="paint_btn">Paint</button>
                    <script data-ai-script-id="broken_script">
                        (() => {
                            const scriptEl = document.currentScript;
                            const ai = window.__aiScriptsManager__.getApi(scriptEl);
                            const boom = ai.protectMutations(() => {
                                throw new Error("boom");
                            });
                            boom();
                        })();
                    </script>
                    <script data-ai-script-id="healthy_script">
                        (() => {
                            const scriptEl = document.currentScript;
                            const ai = window.__aiScriptsManager__.getApi(scriptEl);
                            const sectionEl = scriptEl.closest("section");
                            sectionEl.querySelector(".paint_btn").addEventListener(
                                "click",
                                ai.protectMutations(() => {
                                    sectionEl.querySelector(".target").textContent = "painted";
                                })
                            );
                        })();
                    </script>
                </section>`,
            },
        ]);

        await waitFor(":iframe .ai-html");
        expect.verifySteps(["warning", "notification"]);
        // Only the script that threw is paused.
        expect(":iframe script[data-ai-script-id^='broken_script']").toHaveAttribute(
            "data-ai-script-stopped",
            "1",
        );
        expect(":iframe script[data-ai-script-id^='healthy_script']").not.toHaveAttribute(
            "data-ai-script-stopped",
        );
        // The other script should be running.
        await contains(":iframe .paint_btn").click();
        expect(":iframe .target").toHaveText("painted");
    });

    test("should keep form input names the sanitizer strips as DOM clobbering", async () => {
        await setupWebsiteBuilder("");

        // "name" collides with a form property, so DOMPurify's clobbering
        // guard removes the attribute, yet it is the required field of e.g.
        // crm.lead and project.task, and the stock editor ships it.
        await mockApplyHTML([
            {
                zone: "main",
                mode: "replace",
                content: `<section class="s_website_form">
                    <form data-model_name="crm.lead">
                        <div class="s_website_form_field">
                            <input class="s_website_form_input" type="text" name="name"/>
                        </div>
                    </form>
                </section>`,
            },
        ]);

        expect(":iframe .s_website_form input[name='name']").toHaveCount(1);
    });

    test("should sanitize HTML but keep script tags", async () => {
        await setupAiWebsiteBuilder("");

        await mockApplyHTML([
            {
                zone: "main",
                mode: "replace",
                content: `
                    <?xml version="1.0"?>   <!-- PI -->
                    <message></message>  <!-- Invalid Tag -->
                    <![CDATA[Character Data block]]> <!-- CDATA -->
                    <div id="nested_content">
                        <?xml version="1.0"?>   <!-- PI -->
                        <?xml-stylesheet type="text/xsl" href="style.xsl"?>   <!-- PI -->
                        <message></message>  <!-- Invalid Tag -->
                        <![CDATA[Character Data block]]> <!-- CDATA -->
                        <section id="section_1">Section 1</section>
                        <script data-ai-script-id="nested">window.testScript = true;</script>
                    </div>
                `,
            },
        ]);
        const contentDiv = await waitFor(":iframe #wrap > #nested_content");
        expect(
            [...queryFirst(":iframe #wrap").childNodes, ...contentDiv.childNodes].every((node) =>
                [Node.ELEMENT_NODE, Node.TEXT_NODE].includes(node.nodeType),
            ),
        ).toBe(true, { message: "There should be only element and text nodes" });
        expect(":iframe #wrap > *").toHaveCount(1);
        // The <script> with data-ai-script-id should be kept.
        expect(":iframe script[data-ai-script-id^='nested']").toHaveCount(1);
    });

    test("should run the script when it's inserted", async () => {
        await setupAiWebsiteBuilder(`<section>Section 1</section>`);

        await mockApplyHTML([
            {
                zone: "main",
                mode: "replace",
                selector: "section",
                content:
                    `<section>Section 2` +
                    `<script data-ai-script-id="script_a">` +
                    `(() => {document.currentScript.closest("section").dataset.scriptRan = "1"; })()` +
                    `</script></section>`,
            },
        ]);

        await waitFor(`:iframe section[data-script-ran="1"]`);
        expect(":iframe section > script[data-ai-script-id^='script_a']").toHaveCount(1);
    });

    test("should fold/unfold existing AI chat when leaving/opening editor", async () => {
        mockService("website", {
            get currentWebsite() {
                return {
                    metadata: {
                        mainObject: {
                            model: "website.page",
                        },
                    },
                    default_lang_id: {
                        code: "en_US",
                    },
                };
            },
        });
        await setupWebsiteBuilder("");

        await contains(".o-snippets-top-actions button[data-action='ai-chat']").click();
        await waitFor(".o-mail-ChatWindow");
        await contains(".o-snippets-top-actions button[data-action='ai-chat']").click();
        await waitFor(".o-mail-ChatWindow:nth-child(2)");

        await contains(".o-snippets-top-actions button[data-action='cancel']").click();
        await waitFor(".o-mail-ChatBubble");
        expect(".o-mail-ChatWindow").toHaveCount(0, {
            message: "AI chat windows should fold after leaving editor",
        });

        await contains(".o_edit_website_container button").click();
        expect(".o-mail-ChatWindow").toHaveCount(2, {
            message: "AI chat windows should unfold after re-entering editor",
        });

        mockApplyHTML([
            {
                zone: "main",
                mode: "replace",
                content: `<section id="section_after_navigation"></section>`,
            },
        ]);
        await waitFor(":iframe #wrap > #section_after_navigation");
    });

    test("should unwrap sections if they are wrapped when applying html actions", async () => {
        await setupWebsiteBuilder("");

        await mockApplyHTML([
            {
                zone: "main",
                mode: "replace",
                content: `
                <div class="test-wrapper">
                    <section id="section_1">Section 1</section>
                    <section id="section_2">Section 2</section>
                </div>`,
            },
        ]);

        await waitFor(":iframe #wrap > #section_1");
        expect(":iframe #wrap > section").toHaveCount(2);
        expect(".test-wrapper").toHaveCount(0);
    });

    test("should not crash when editing an element already removed", async () => {
        await setupWebsiteBuilder(`<section></section>`);

        await mockApplyHTML([
            {
                zone: "main",
                mode: "replace",
                selector: "section",
                content: `<section class="a"></section>`,
            },
            {
                zone: "main",
                mode: "replace",
                selector: "section",
                content: `<section class="b"></section>`,
            },
        ]);

        await waitFor(":iframe #wrap > section.a");
    });

    test("should disable AI chat button on pages not linked to website.page record", async () => {
        // Simulate a non-editable page
        mockService("website", {
            get currentWebsite() {
                return {
                    metadata: {
                        mainObject: {
                            model: "ir.ui.view",
                        },
                    },
                    default_lang_id: {
                        code: "en_US",
                    },
                };
            },
        });
        await setupWebsiteBuilder();
        expect(".o-snippets-top-actions button[data-action='ai-chat']").toHaveAttribute("disabled");
    });

    test("should disable AI chat button for restricted editors", async () => {
        mockService("website", {
            get isDesigner() {
                return false;
            },
            get currentWebsite() {
                return {
                    metadata: {
                        mainObject: {
                            model: "website.page",
                        },
                    },
                    default_lang_id: {
                        code: "en_US",
                    },
                };
            },
        });
        await setupWebsiteBuilder();
        expect(".o-snippets-top-actions button[data-action='ai-chat']").toHaveAttribute("disabled");
    });

    test("should hide AI chat button in translation mode", async () => {
        await setupSidebarBuilderForTranslation({});
        expect(".o-snippets-top-actions button[data-action='ai-chat']").toHaveCount(0);
    });

    test("should flag as AI content each block replacing a zone", async () => {
        await setupWebsiteBuilder("");

        await mockApplyHTML([
            {
                zone: "main",
                mode: "replace",
                content: `
                <div class="test-wrapper">
                    <section id="section_1"><div id="nested_1">Section 1</div></section>
                    <section id="section_2">Section 2</section>
                </div>`,
            },
        ]);

        await waitFor(":iframe #wrap > #section_1");
        expect(":iframe #wrap").toHaveAttribute("data-contains-ai-content", "true");
        expect(":iframe #wrap > #section_1").toHaveAttribute("data-contains-ai-content", "true");
        expect(":iframe #wrap > #section_2").toHaveAttribute("data-contains-ai-content", "true");
        // Only the generated blocks are flagged, not their content.
        expect(":iframe #nested_1").not.toHaveAttribute("data-contains-ai-content");
    });

    test("should flag as AI content each block inserted at a selector", async () => {
        await setupWebsiteBuilder(
            `<section id="target_1"></section>
             <section id="target_2"></section>
             <section id="target_3"></section>`,
        );

        await mockApplyHTML([
            {
                zone: "main",
                mode: "before",
                selector: "#target_1",
                content: `<section id="before_1"><div id="nested_2"></div></section>
                          <section id="before_2"></section>`,
            },
            {
                zone: "main",
                mode: "after",
                selector: "#target_2",
                content: `<section id="after_1"></section>`,
            },
            {
                zone: "main",
                mode: "replace",
                selector: "#target_3",
                content: `<section id="replace_1"></section>`,
            },
        ]);

        await waitFor(":iframe #wrap > #replace_1");
        for (const id of ["before_1", "before_2", "after_1", "replace_1"]) {
            expect(`:iframe #wrap > #${id}`).toHaveAttribute("data-contains-ai-content", "true");
        }
        // Only the generated blocks are flagged, not their content.
        expect(":iframe #nested_2").not.toHaveAttribute("data-contains-ai-content");
        // Untouched blocks are not flagged.
        expect(":iframe #wrap > #target_1").not.toHaveAttribute("data-contains-ai-content");
        expect(":iframe #wrap > #target_2").not.toHaveAttribute("data-contains-ai-content");
    });

    test("should report errors with CSS selector", async () => {
        await setupWebsiteBuilder(`<section id="dummy"></section>`);

        const mockResponse = await mockApplyHTML([
            {
                zone: "main",
                mode: "after",
                selector: ".dummy",
                content: `<section id="new"></section>`,
            },
            {
                zone: "main",
                mode: "after",
                selector: "dummy!",
                content: `<section id="new"></section>`,
            },
            {
                zone: "footer",
                mode: "replace",
                selector: "#footer",
                content: `<section id="new"></section>`,
            },
        ]);
        expect(mockResponse[0].error).toBe("Nothing matches .dummy");
        expect(mockResponse[1].error).toBe("Invalid CSS selector: dummy!");
        expect(mockResponse[2].error).toBe("Zone element not found for zone: footer");
        expect(":iframe #new").toHaveCount(0);
    });

    test("should report the sanitized html when content was dropped", async () => {
        await setupWebsiteBuilder(`<section id="target"></section>`);

        const mockResponse = await mockApplyHTML([
            {
                zone: "main",
                mode: "after",
                selector: "#target",
                content: `<div class="new" onclick="alert(1)"></div>`,
            },
            {
                zone: "main",
                mode: "after",
                selector: "#target",
                content: `<iframe class="new"></iframe>`,
            },
            {
                zone: "main",
                mode: "after",
                selector: "#target",
                content: `<!-- COMMENT -->`,
            },
        ]);

        // Dropped attribute "onclick": what is left is reported back.
        expect(mockResponse[0].sanitizer_note).toInclude("`sanitized_html` is what is actually");
        expect(mockResponse[0].sanitized_html).toBe('<div class="new"></div>');
        // No error means applied.
        expect(mockResponse[0].error).toBe(undefined);

        // Dropped element "iframe": nothing is left.
        expect(mockResponse[1].error).toBe("Everything was dropped by the sanitizer");
        expect(mockResponse[1].sanitized_html).toBe(undefined);

        // Dropped comment
        expect(mockResponse[2].error).toBe("Everything was dropped by the sanitizer");
        expect(mockResponse[2].sanitized_html).toBe(undefined);
        expect(":iframe iframe.new").toHaveCount(0);

        expect(":iframe div.new").toHaveCount(1);
        expect(":iframe div[onclick]").toHaveCount(0);
    });
});

describe("AI Website form action tool", () => {
    const FORM_MODELS = [
        {
            id: 85,
            model: "mail.mail",
            name: "Outgoing Mails",
            website_form_label: "Send an E-mail",
            website_form_key: "send_mail",
        },
        {
            id: 687,
            model: "hr.applicant",
            name: "Applicant",
            website_form_label: "Apply for a Job",
            website_form_key: "apply_job",
        },
    ];
    const FORM_HTML = `
        <section class="s_website_form" data-snippet="s_website_form">
            <form data-model_name="mail.mail">
                <div class="s_website_form_rows">
                    <div class="s_website_form_field s_website_form_custom" data-type="char">
                        <label class="s_website_form_label" style="width: 200px">
                            <span class="s_website_form_label_content">My question</span>
                        </label>
                        <input class="s_website_form_input" name="My question"/>
                    </div>
                </div>
                <div class="s_website_form_submit">
                    <div class="s_website_form_label"/>
                    <a class="s_website_form_send">Send</a>
                </div>
            </form>
        </section>`;

    function mockSetFormAction(params) {
        const setFormAction = aiClientToolsRegistry.get("website_set_form_action", null);
        return setFormAction?.(null, params);
    }

    beforeEach(() => {
        patchWithCleanup(webModels.IrModel.prototype, {
            get_compatible_form_models: () => FORM_MODELS,
        });
        onRpc("get_authorized_fields", ({ args }) =>
            args[0] === "hr.applicant"
                ? {
                      partner_name: {
                          name: "partner_name",
                          string: "Your Name",
                          type: "char",
                          required: true,
                      },
                  }
                : { email_to: { name: "email_to", string: "Email To", type: "char" } }
        );
    });

    test("switches the form's action like the editor", async () => {
        await setupWebsiteBuilder(FORM_HTML, { loadIframeBuilderTemplates: true });
        const result = await mockSetFormAction({
            selector: "section.s_website_form",
            action_key: "apply_job",
            fields: [],
        });
        expect(":iframe form").toHaveAttribute("data-model_name", "hr.applicant");
        expect(":iframe input[name='partner_name']").toHaveCount(1);
        expect(":iframe input[name='My question']").toHaveCount(0);
        expect(result.previous_form_html).toInclude('name="My question"');
        expect(result.form_html).toInclude("partner_name");
    });

    test("a destination-only call sets the hidden field without re-rendering", async () => {
        await setupWebsiteBuilder(FORM_HTML, { loadIframeBuilderTemplates: true });
        const result = await mockSetFormAction({
            selector: "section.s_website_form",
            action_key: "send_mail",
            fields: [
                { name: "email_to", value: "boss@example.com" },
                { name: "not_a_field", value: "x" },
            ],
        });
        expect(":iframe input[name='My question']").toHaveCount(1);
        expect(":iframe .s_website_form_dnone input[name='email_to']").toHaveValue(
            "boss@example.com"
        );
        expect(result.previous_form_html).toBe(undefined);
        expect(result.form_html).toInclude('name="My question"');
        const emailDestination = result.destination_fields.find((f) => f.name === "email_to");
        expect(emailDestination.prefilled_value).toBe("boss@example.com");
        expect(result.field_errors.length).toBe(1);
        expect(result.field_errors[0]).toInclude("not_a_field");
    });

    test("reports an error for an unknown action or a missing form", async () => {
        await setupWebsiteBuilder(FORM_HTML);
        let result = await mockSetFormAction({
            selector: "section.s_website_form",
            action_key: "no_such_action",
            fields: [],
        });
        expect(result.error).toInclude('Unknown form action "no_such_action"');
        expect(result.error).toInclude("send_mail");
        result = await mockSetFormAction({
            selector: ".not-on-the-page",
            action_key: "send_mail",
            fields: [],
        });
        expect(result.error).toInclude("No website form matches");
    });
});

describe("AI chat messages posting", () => {
    function notifySession(channelId, sessionId, values) {
        const [channel] = MockServer.env["discuss.channel"].search_read([["id", "=", channelId]]);
        MockServer.env["bus.bus"]._sendone(channel, "mail.record/insert", {
            "ai.session": [{ id: sessionId, ...values }],
        });
    }

    const currentWebsite = {
        id: 1,
        metadata: {
            title: "Test AI Website",
            lang: "en_US",
            direction: "ltr",
            location: "/test-path",
            mainObject: {
                model: "website.page",
                id: 1,
            },
        },
        default_lang_id: {
            code: "en_US",
        },
    };
    beforeEach(() => {
        mockService("website", {
            get contentWindow() {
                return {
                    location: {
                        pathname: "/test-path",
                    },
                };
            },
            get pageDocument() {
                return queryFirst(":iframe");
            },
            get currentWebsite() {
                return currentWebsite;
            },
        });
    });

    test("should send page context", async () => {
        await setupWebsiteBuilder("main content", {
            footerContent: '<footer id="bottom"><div id="footer">footer content</div></footer>',
        });

        onRpc("/ai/start_session_advance", async (request) => {
            const { params } = await request.json();
            const pageInfo = params.current_view_info.website_page;
            expect(pageInfo.title).toBe("Test AI Website");
            expect(pageInfo.lang).toBe("en_US");
            expect(pageInfo.direction).toBe("ltr");
            expect(pageInfo.location).toBe("/test-path");
            // Identifies the page, so that edits made for it never land on another one.
            expect(pageInfo.main_object).toEqual({ model: "website.page", id: 1 });
            expect(pageInfo.is_page_ai_editable).toBe(true);
            expect(pageInfo.editable_zones.main).toBe("main content");
            expect(pageInfo.editable_zones.footer).toBe("footer content");
            expect(pageInfo.css_variables["o-cc1-bg"]).not.toBe(undefined);
            expect(pageInfo.css_variables["o-cc5-bg"]).not.toBe(undefined);
            expect.step("start_session_advance");
            return { loop_state: "waiting_model" };
        });

        await contains(".o-snippets-top-actions button[data-action='ai-chat']").click();

        await contains(".o-mail-Composer-input").edit("Hello");
        await contains(".o-mail-Composer-input").press("Enter");

        await expect.waitForSteps(["start_session_advance"]);
    });

    test("should finalize a full-page build through the finalize_website_page client tool", async () => {
        await setupWebsiteBuilder("");
        authenticate("admin", "admin");
        onRpc("/website/theme_customize_bundle_reload", () => true);

        let channelId;
        let sessionId;
        const resumeToken = "finalize-page-token";
        onRpc("/ai/start_session_advance", async (request) => {
            const { params } = await request.json();
            channelId = params.channel_id;
            [sessionId] = MockServer.env["ai.session"].search([["channel_id", "=", channelId]]);
            expect("response" in params).toBe(false);
            expect.step("start_session_advance");
            return { loop_state: "waiting_model" };
        });
        onRpc("/ai/resume_pending_interaction", async (request) => {
            const { params } = await request.json();
            expect(params.channel_id).toBe(channelId);
            expect(params.session_id).toBe(sessionId);
            expect(params.resume_token).toBe(resumeToken);
            expect("mail_message_id" in params).toBe(false);
            expect(params.response).toEqual({
                kind: "client_result",
                value: {
                    note: "Page ready",
                    actions: [{ description: "replace in main" }],
                },
            });
            expect.step("client result submitted");
            return { loop_state: "ready" };
        });
        onRpc("/ai_website/finalize_page", async (request) => {
            const { params } = await request.json();
            expect(params.html).toBe(`<section id="built"></section>`);
            return { html: `<section id="finalized"></section>` };
        });

        await contains(".o-snippets-top-actions button[data-action='ai-chat']").click();
        await contains(".o-mail-Composer-input").edit("Build my page");
        await contains(".o-mail-Composer-input").press("Enter");
        await expect.waitForSteps(["start_session_advance"]);

        notifySession(channelId, sessionId, {
            loop_state: "waiting_client_result",
            clientToolRequest: {
                aiSessionIdentifier,
                name: "finalize_website_page",
                params: {
                    html: `<section id="built"></section>`,
                    note: "Page ready",
                },
                resumeToken,
            },
        });

        await waitFor(":iframe #wrap > #finalized");
        await expect.waitForSteps(["client result submitted"]);
    });

    for (const failFinalization of [false, true]) {
        test(`should resume a scraped page build when finalization ${failFinalization ? "fails" : "succeeds"}`, async () => {
            const { getEditor } = await setupWebsiteBuilder("");
            authenticate("admin", "admin");
            onRpc("/website/theme_customize_bundle_reload", () => true);
            const finalization = Promise.withResolvers();
            const resumeToken = "scrape-token";
            const clientToolToken = "finalize-scraped-page-token";
            let channelId;
            let sessionId;
            let ready = false;
            let payload;
            let resumeAttempts = 0;
            onRpc("/ai_website/ready_scraper_results", () => ready ? [payload] : []);
            onRpc("/ai/start_session_advance", async (request) => {
                const { params } = await request.json();
                channelId = params.channel_id;
                [sessionId] = MockServer.env["ai.session"].search([["channel_id", "=", channelId]]);
                expect.step("scraping");
                return { loop_state: "waiting_model" };
            });
            onRpc("/ai/resume_pending_interaction", async (request) => {
                const { params } = await request.json();
                expect(params.channel_id).toBe(channelId);
                expect(params.session_id).toBe(sessionId);
                expect(params.ai_session_identifier).toBe(aiSessionIdentifier);
                if (params.response.kind === "async") {
                    expect(params.resume_token).toBe(resumeToken);
                    expect(params.response).toEqual({ kind: "async", call_id: "scrape-1" });
                    expect(params.current_view_info.website_page.main_object).toEqual(
                        payload.target_page.main_object
                    );
                    expect(params.current_view_info.website_page.editable_zones.main).toInclude(
                        'id="edited_while_scraping"'
                    );
                    resumeAttempts++;
                    ready = false;
                    expect.step("continue after scraping");
                    return { loop_state: "waiting_model", interactionConsumed: true };
                }
                expect(params.resume_token).toBe(clientToolToken);
                expect(params.response).toEqual(
                    failFinalization
                        ? { kind: "client_error", value: "Finalization failed" }
                        : {
                              kind: "client_result",
                              value: {
                                  note: "Page ready",
                                  actions: [{ description: "replace in main" }],
                              },
                          }
                );
                expect.step("resumed");
                return { loop_state: "ready", interactionConsumed: true };
            });
            const plugin = getEditor().plugins.find(
                (plugin) => plugin.constructor.id === "aiWebsiteBuilder"
            );
            if (failFinalization) {
                patchWithCleanup(plugin, {
                    async finalizePage() {
                        expect(channel.isAiGenerating).toBe(true);
                        expect.step("finalizing");
                        await finalization.promise;
                        throw new Error("Finalization failed");
                    },
                });
            } else {
                onRpc("/ai_website/finalize_page", () => {
                    expect(channel.isAiGenerating).toBe(true);
                    expect.step("finalizing");
                    return finalization.promise;
                });
            }
            await contains(".o-snippets-top-actions button[data-action='ai-chat']").click();
            await contains(".o-mail-Composer-input").edit("Build a page from my reference");
            await contains(".o-mail-Composer-input").press("Enter");
            await expect.waitForSteps(["scraping"]);

            const channel = plugin.services["mail.store"]["discuss.channel"].get(channelId);
            payload = {
                channel_id: channelId,
                session_id: sessionId,
                resume_token: resumeToken,
                target_page: { main_object: { model: "website.page", id: 1 } },
                tool_call_id: "scrape-1",
            };
            notifySession(channelId, sessionId, {
                loop_state: "waiting_external_result",
                external_pending_tool: true,
                resume_token: resumeToken,
            });
            await waitUntil(() => !channel.isAiGenerating);
            await waitForNone(".o_builder_disabled");
            expect(":iframe .o_loading_screen").toHaveCount(0);

            // Resuming must send the current editor contents, not the original request's snapshot.
            await mockApplyHTML([{
                zone: "main", mode: "replace", content: '<section id="edited_while_scraping"></section>',
            }]);
            // A different editor must not resume the pending request.
            await plugin.resumeAfterScraping({
                ...payload,
                target_page: { main_object: { model: "website.page", id: 2 } },
            });
            ready = true;
            MockServer.env["bus.bus"]._sendone("broadcast", "ai_website/scraper_result_ready", payload);
            MockServer.env["bus.bus"]._sendone("broadcast", "ai_website/scraper_result_ready", payload);
            await expect.waitForSteps(["continue after scraping"]);
            await waitUntil(() => plugin.scraperResumes.size === 0);
            await waitFor(".o_builder_disabled");
            expect(channel.isAiGenerating).toBe(true);
            await advanceTime(1500);
            expect(":iframe .o_loading_screen").toHaveClass("o_we_ui_loading");

            // The resumed model round delivers its client tool through the bus.
            notifySession(channelId, sessionId, {
                loop_state: "waiting_client_result",
                external_pending_tool: false,
                resume_token: clientToolToken,
                clientToolRequest: {
                    aiSessionIdentifier,
                    name: "finalize_website_page",
                    params: { html: "<section>Reference</section>", note: "Page ready" },
                    resumeToken: clientToolToken,
                },
            });
            await expect.waitForSteps(["finalizing"]);
            expect(".o_builder_disabled").toHaveCount(1);
            expect(":iframe .o_loading_screen").toHaveClass("o_we_ui_loading");
            finalization.resolve({ html: '<section id="scraped_page"></section>' });
            await expect.waitForSteps(["resumed"]);
            await waitUntil(() => !channel.isAiGenerating);
            await waitForNone(".o_builder_disabled");
            expect(":iframe .o_loading_screen").toHaveCount(0);
            expect(resumeAttempts).toBe(1);
            if (!failFinalization) {
                expect(":iframe #wrap > #scraped_page").toHaveCount(1);
            }
        });
    }

    test("should recover a saved scraping result on editor open and retry a busy session", async () => {
        const pyEnv = await startServer();
        authenticate("admin", "admin");
        pyEnv["website"].create({});
        const { ai_channel_id: channelId } = pyEnv["ai.agent"].action_launch_ai_chat("website_builder_ai");
        const [sessionId] = pyEnv["ai.session"].search([["channel_id", "=", channelId]]);
        const resumeToken = "saved-scrape-token";
        const clientToolToken = "recovered-page-token";
        pyEnv["ai.session"].write([sessionId], {
            loop_state: "waiting_external_result",
            external_pending_tool: true,
            resume_token: resumeToken,
        });
        const payload = {
            channel_id: channelId, session_id: sessionId, resume_token: resumeToken,
            tool_call_id: "saved-scrape",
            target_page: { main_object: { model: "website.page", id: 1 }, website_id: 1 },
        };
        const busyResponse = Promise.withResolvers();
        let ready = true;
        let attempts = 0;
        onRpc("/ai_website/ready_scraper_results", async (request) => {
            const { params } = await request.json();
            expect(params).toEqual({ website_id: 1, main_object: payload.target_page.main_object });
            return ready ? [payload] : [];
        });
        onRpc("/ai/resume_pending_interaction", async (request) => {
            const { params } = await request.json();
            expect(params.channel_id).toBe(channelId);
            expect(params.session_id).toBe(sessionId);
            if (params.response.kind !== "async") {
                expect(params.resume_token).toBe(clientToolToken);
                expect(params.response).toEqual({
                    kind: "client_result", value: [{ description: "replace in main" }],
                });
                expect(".o_builder_disabled").toHaveCount(1);
                expect.step("applied");
                return { loop_state: "ready", interactionConsumed: true };
            }
            expect(params.resume_token).toBe(resumeToken);
            expect(params.response).toEqual({ kind: "async", call_id: "saved-scrape" });
            attempts++;
            // A busy row lock leaves the result unconsumed, so recovery retries it.
            ready = attempts === 1;
            expect.step(ready ? "busy" : "resumed");
            if (ready) {
                // Keep recovery pending until editor setup and the busy assertion finish.
                await busyResponse.promise;
            }
            return {
                loop_state: ready ? "waiting_external_result" : "waiting_model",
                interactionConsumed: !ready,
            };
        });
        const { getEditor } = await setupWebsiteBuilder("", { hasToCreateWebsite: false });
        const plugin = getEditor().plugins.find((p) => p.constructor.id === "aiWebsiteBuilder");
        await expect.waitForSteps(["busy"]);
        busyResponse.resolve();
        await waitUntil(() => plugin.scraperResumes.size === 0);
        expect(".o_builder_disabled").toHaveCount(0);
        await advanceTime(5000);
        await expect.waitForSteps(["resumed"]);
        await waitUntil(() => plugin.scraperResumes.size === 0);
        await waitFor(".o_builder_disabled");
        // This tool acquires the builder mutex: the resumed turn must leave it free.
        notifySession(channelId, sessionId, {
            loop_state: "waiting_client_result",
            external_pending_tool: false,
            resume_token: clientToolToken,
            clientToolRequest: {
                aiSessionIdentifier,
                name: "website_apply_html",
                params: {
                    actions: [
                        { zone: "main", mode: "replace", content: '<section id="recovered"></section>' },
                    ],
                    target_page: payload.target_page,
                },
                resumeToken: clientToolToken,
            },
        });
        await expect.waitForSteps(["applied"]);
        await waitForNone(".o_builder_disabled");
        await advanceTime(5000);
        expect(attempts).toBe(2);
        expect(":iframe #recovered").toHaveCount(1);
        expect(":iframe .o_loading_screen").toHaveCount(0);
    });

    test("should recover a scraping notification missed before reconnecting", async () => {
        const pyEnv = await startServer();
        pyEnv["website"].create({});
        const { ai_channel_id: channelId } = pyEnv["ai.agent"].action_launch_ai_chat("website_builder_ai");
        const [sessionId] = pyEnv["ai.session"].search([["channel_id", "=", channelId]]);
        const resumeToken = "reconnected-scrape-token";
        pyEnv["ai.session"].write([sessionId], {
            loop_state: "waiting_external_result",
            external_pending_tool: true,
            resume_token: resumeToken,
        });
        let ready = false;
        onRpc("/ai_website/ready_scraper_results", () => ready ? [{
            channel_id: channelId, session_id: sessionId, resume_token: resumeToken,
            tool_call_id: "reconnected-scrape",
            target_page: { main_object: { model: "website.page", id: 1 }, website_id: 1 },
        }] : []);
        onRpc("/ai/resume_pending_interaction", async (request) => {
            const { params } = await request.json();
            expect(params.channel_id).toBe(channelId);
            expect(params.session_id).toBe(sessionId);
            expect(params.resume_token).toBe(resumeToken);
            expect(params.response).toEqual({ kind: "async", call_id: "reconnected-scrape" });
            ready = false;
            expect.step("resumed");
            return { loop_state: "ready", interactionConsumed: true };
        });
        const { getEditor } = await setupWebsiteBuilder("", { hasToCreateWebsite: false });
        const plugin = getEditor().plugins.find((p) => p.constructor.id === "aiWebsiteBuilder");
        await waitUntil(() => !plugin.recoveringScraperResults);
        ready = true;
        // Deliver the worker's reconnect event, without the scraping notification.
        plugin.services.bus_service.handleMessage({ data: { type: "BUS:RECONNECT" } });
        await expect.waitForSteps(["resumed"]);
    });

    test("should send only the selected website elements in page context", async () => {
        await setupWebsiteBuilder(`
            <section class="s_text_block" data-snippet="s_text_block" data-name="First profile">
                <div class="container"><p>Jordan Ellis</p></div>
            </section>
            <section class="s_text_block" data-snippet="s_text_block" data-name="Second profile">
                <div class="container"><p>Avery Morgan</p></div>
            </section>
            <section class="s_text_block" data-snippet="s_text_block" data-name="Third profile">
                <div class="container"><p>Noah Brooks</p></div>
            </section>
            <section class="s_text_block" data-snippet="s_text_block" data-name="Fourth profile">
                <div class="container"><p>Mia Thompson</p></div>
            </section>
        `);

        onRpc("/ai/start_session_advance", async (request) => {
            const { params } = await request.json();
            const pageInfo = params.current_view_info.website_page;
            const selectedElements = pageInfo.selected_elements;
            expect(selectedElements.map(({ tag, text }) => ({ tag, text }))).toEqual([
                { tag: "section", text: "Jordan Ellis" },
                { tag: "section", text: "Noah Brooks" },
            ]);
            expect(selectedElements[0].computed_style.display).toBe("block");
            for (const { id } of selectedElements) {
                expect(pageInfo.editable_zones.main).toInclude(`data-ai-id="${id}"`);
            }
            expect.step("start_session_advance");
            return { loop_state: "waiting_model" };
        });

        await contains(".o-snippets-top-actions button[data-action='ai-chat']").click();
        await contains(".o-mail-Composer button[title='More Actions']").click();
        await contains(".o-dropdown-item:text('Select Elements')").click();
        await contains(":iframe section[data-name='First profile']").click();
        await contains(":iframe section[data-name='Third profile']").click();

        await contains(".o-mail-Composer-input").edit("Update these profiles");
        await contains(".o-mail-Composer-input").press("Enter");

        await expect.waitForSteps(["start_session_advance"]);
    });

    // This test ensures that the patch on Thread.post doesn't break the sending
    // of attachments, which would happen if ever an await is added before the
    // call to super.post().
    test("should send attachments", async () => {
        onRpc("/ai/start_session_advance", () => ({
            loop_state: "waiting_model",
        }));

        await setupWebsiteBuilder("");

        await contains(".o-snippets-top-actions button[data-action='ai-chat']").click();
        await waitFor(".o-mail-ChatWindow");

        const file = new File([""], "image.png", { type: "image/png" });
        await dragenterFiles(".o-mail-Composer-input", [file]);
        await dropFiles(".o-Dropzone", [file]);
        await waitFor(".o-mail-AttachmentContainer");

        await contains(".o-mail-ActionList-button[name='send-message']").click();

        await waitFor(".o-mail-Message .o-mail-AttachmentImage");
    });
});

describe("External image localization on save", () => {
    const EXTERNAL_IMG = "https://other-site.example.com/hero.png";
    const EXTERNAL_BG = "https://other-site.example.com/pattern.png";
    const LOCAL_IMG = "/web/image/1-abcdef/local.png";
    const content =
        `<img class="external" src="${EXTERNAL_IMG}"/>` +
        `<img class="local" src="${LOCAL_IMG}"/>` +
        `<div class="bg" style="background-image: url('${EXTERNAL_BG}');"></div>` +
        `<div class="bg-shorthand" style="background: url('${EXTERNAL_BG}') center / cover;"></div>`;

    async function applyAiContent() {
        await aiClientToolsRegistry.get("website_apply_html")(null, {
            actions: [
                { zone: "main", mode: "replace", content: `<section id="s">${content}</section>` },
            ],
        });
        await waitFor(":iframe #wrap > #s");
    }

    test("should copy the external images into Odoo when the page is saved", async () => {
        const { getEditor } = await setupAiWebsiteBuilder("");
        onRpc("ir.ui.view", "save", () => true);
        onRpc("/ai_website/localize_external_images", async (request) => {
            const { params } = await request.json();
            // Only the external URLs are sent, and each one only once.
            expect(params.urls.toSorted()).toEqual([EXTERNAL_BG, EXTERNAL_IMG].toSorted());
            expect.step("localize");
            return {
                sources: {
                    [EXTERNAL_IMG]: "/web/image/11-aaa/hero.png",
                    [EXTERNAL_BG]: "/web/image/12-bbb/pattern.png",
                },
                errors: {},
            };
        });

        await applyAiContent();
        // Only the images hosted elsewhere are flagged for the save.
        expect(":iframe #s .o_external_image_to_save").toHaveCount(3);
        expect(":iframe img.local").not.toHaveClass("o_external_image_to_save");

        await getEditor().shared.savePlugin.save();

        await expect.waitForSteps(["localize"]);
        expect(":iframe img.external").toHaveAttribute("src", "/web/image/11-aaa/hero.png");
        expect(":iframe img.local").toHaveAttribute("src", LOCAL_IMG);
        expect(queryFirst(":iframe .bg").style.backgroundImage).toInclude(
            "/web/image/12-bbb/pattern.png"
        );
        expect(queryFirst(":iframe .bg-shorthand").style.backgroundImage).toInclude(
            "/web/image/12-bbb/pattern.png"
        );
        // Nothing left to localize, so a later save does not try again.
        expect(":iframe #s .o_external_image_to_save").toHaveCount(0);
    });

    test("should keep the page working and warn when an image cannot be copied", async () => {
        const notifications = [];
        mockService("notification", {
            add: (message, options) => notifications.push({ message, options }),
        });
        const { getEditor } = await setupAiWebsiteBuilder("");
        onRpc("ir.ui.view", "save", () => true);
        onRpc("/ai_website/localize_external_images", () => ({
            sources: { [EXTERNAL_BG]: "/web/image/12-bbb/pattern.png" },
            errors: { [EXTERNAL_IMG]: "URL does not point to a supported image." },
        }));

        await applyAiContent();
        await getEditor().shared.savePlugin.save();

        // A third-party host being unusable must not cost the user their save.
        expect(":iframe img.external").toHaveAttribute("src", EXTERNAL_IMG);
        expect(queryFirst(":iframe .bg").style.backgroundImage).toInclude(
            "/web/image/12-bbb/pattern.png"
        );
        // The flag stays only on what is still external, so the next save retries it.
        expect(":iframe #s .o_external_image_to_save").toHaveCount(1);
        expect(":iframe img.external").toHaveClass("o_external_image_to_save");
        expect(notifications).toHaveLength(1);
        expect(notifications[0].options.type).toBe("warning");
    });
});
