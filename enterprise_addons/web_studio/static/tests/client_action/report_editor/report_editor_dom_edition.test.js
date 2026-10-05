import { setupEditor } from "@html_editor/../tests/_helpers/editor";
import { getContent, setSelection } from "@html_editor/../tests/_helpers/selection";
import { insertText } from "@html_editor/../tests/_helpers/user_actions";
import { before, describe, expect, test } from "@odoo/hoot";
import { contains, defineModels, fields, models } from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { hover, queryAll, queryFirst, queryOne, waitFor } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import { REPORT_EDITOR_PLUGINS } from "@web_studio/client_action/report_editor/report_editor_wysiwyg/editor_plugins/report_editor_plugin";

describe.current.tags("desktop");

class SomeModel extends models.Model {
    _name = "some.model";

    field = fields.Char({ string: "My little field" });
}

defineModels([SomeModel]);

before(() => {
    const services = registry.category("services");
    for (const [name] of services.getEntries()) {
        if (
            name.startsWith("mail.") ||
            name.startsWith("discuss.") ||
            ["bus.connection_alert", "bus.monitoring_service"].includes(name)
        ) {
            services.remove(name);
        }
    }
    services.remove("im_status");

    const main_components = registry.category("main_components");
    for (const [name] of main_components.getEntries()) {
        if (name.startsWith("mail.") || name.startsWith("discuss.") || name.startsWith("bus.")) {
            main_components.remove(name);
        }
    }
});

function getEditorOptions() {
    return {
        config: {
            basePlugins: REPORT_EDITOR_PLUGINS,
            dynamicResModel: "some.model",
        },
        props: {
            iframe: true,
            copyCss: true,
        },
    };
}

test("add column", async () => {
    const { editor } = await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1[]</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    await hover(queryFirst(":iframe q-th"));
    await contains(".o-overlay-container .o-we-table-menu").click();
    await contains(".o-dropdown-item:contains(Insert Right)").click();

    expect(getContent(editor.getElContent().firstElementChild)).toBe(`
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th><q-th><div><br></div></q-th>
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1</q-td><q-td><div><br></div></q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td><q-td><div><br></div></q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td><q-td><div><br></div></q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table>`);
});

test("add column non-matching conditionals", async () => {
    const { editor } = await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th t-if="true">HEAD2</q-th>
                    <q-th t-else="">HEAD3</q-th>
                    <q-th>HEAD4</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <t t-if="true">
                    <q-tr>
                        <q-td>1</q-td>
                        <q-td>2</q-td>
                        <q-td>4</q-td>
                    </q-tr>
                </t>
                <t t-else="">
                    <q-tr>
                        <q-td>1</q-td>
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </q-tr>
                </t>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    await hover(queryFirst(":iframe q-th:last-child"));
    await contains(".o-overlay-container .o-we-table-menu").click();
    await contains(".o-dropdown-item:contains(Insert Right)").click();

    expect(getContent(editor.getElContent().firstElementChild)).toBe(`
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th t-if="true">HEAD2</q-th>
                    <q-th t-else="">HEAD3</q-th>
                    <q-th>HEAD4</q-th><q-th><div><br></div></q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <t t-if="true">
                    <q-tr>
                        <q-td>1</q-td>
                        <q-td>2</q-td>
                        <q-td>4</q-td><q-td><div><br></div></q-td>
                    </q-tr>
                </t>
                <t t-else="">
                    <q-tr>
                        <q-td>1</q-td>
                        <q-td>3</q-td>
                        <q-td>4</q-td><q-td><div><br></div></q-td>
                    </q-tr>
                </t>
            </q-tbody>
        </q-table>`);
});

test("remove column", async () => {
    const { editor } = await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1[]</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );
    await hover(queryFirst(":iframe q-th"));
    await contains(".o-overlay-container .o-we-table-menu").click();
    await contains(".o-dropdown-item:contains(Delete)").click();

    const el = editor.getElContent();
    expect(getContent(el.firstElementChild)).toBe(`
        <q-table>
            <q-thead>
                <q-tr>
${"                    "}
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
${"                        "}
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
${"                        "}
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
${"                    "}
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table>`);
});

test("remove last column does not crash", async () => {
    const { editor } = await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <q-td>1[]</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    await hover(queryFirst(":iframe q-th"));
    await contains(".o-overlay-container .o-we-table-menu").click();
    await contains(".o-dropdown-item:contains(Delete)").click();

    const el = editor.getElContent();
    expect(getContent(el.firstElementChild)).toBe(`
        <q-table>
            <q-thead>
                <q-tr>
${"                    "}
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
${"                    "}
                </q-tr>
            </q-tbody>
        </q-table>`);
});

test("remove column colspan", async () => {
    const { editor, el } = await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th>HEAD2</q-th>
                    <q-th>HEAD3</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td colspan="2">1[]</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td colspan="2">3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td colspan="2">6</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    await setSelection({ anchorNode: queryFirst(":iframe q-td"), anchorOffset: 1 });
    expect(getContent(el.querySelector("div"))).toBe(`
        <q-table class="oe_unbreakable" style="--q-table-col-count: 3;">
            <q-thead class="oe_unbreakable">
                <q-tr class="oe_unbreakable">
                    <q-th class="oe_unbreakable">HEAD1</q-th>
                    <q-th class="oe_unbreakable">HEAD2</q-th>
                    <q-th class="oe_unbreakable">HEAD3</q-th>
                </q-tr>
            </q-thead>
            <q-tbody class="oe_unbreakable">
                <q-tr class="oe_unbreakable">
                    <t t-if="true" data-oe-t-inline="true" data-oe-t-group="0" data-oe-t-selectable="true" data-oe-t-group-active="true">
                        <q-td colspan="2" class="oe_unbreakable" style="--q-cell-col-size: 2;">1[]</q-td>
                        <q-td class="oe_unbreakable">2</q-td>
                    </t>
                    <t t-else="" data-oe-t-inline="true" data-oe-t-selectable="true" data-oe-t-group="0">
                        <q-td colspan="2" class="oe_unbreakable" style="--q-cell-col-size: 2;">3</q-td>
                        <q-td class="oe_unbreakable">4</q-td>
                    </t>
                </q-tr>
                <q-tr class="oe_unbreakable">
                    <q-td class="oe_unbreakable">5</q-td>
                    <q-td colspan="2" class="oe_unbreakable" style="--q-cell-col-size: 2;">6</q-td>
                </q-tr>
            </q-tbody>
        </q-table>`);

    await hover(queryAll(":iframe q-th")[1]);
    await contains(".o-overlay-container .o-we-table-menu").click();
    await contains(".o-dropdown-item:contains(Delete)").click();

    const cleanedEl = editor.getElContent();
    expect(getContent(cleanedEl.firstElementChild)).toBe(`
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
${"                    "}
                    <q-th>HEAD3</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table>`);
});

test("move outside table menu must remove it if the menu is close", async () => {
    await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1[]</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    await hover(queryAll(":iframe q-th")[1]);
    await animationFrame();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(1);

    await hover(":iframe q-table");
    await animationFrame();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(0);
});

test("move outside table menu shouldn't remove it if the menu is close, we should click to close it", async () => {
    await setupEditor(
        `<div style="width: 100px; margin-top: 50px; margin-left: 50px;">
        <q-table>
            <q-thead>
                <q-tr>
                    <q-th>HEAD1</q-th>
                    <q-th>HEAD2</q-th>
                </q-tr>
            </q-thead>
            <q-tbody>
                <q-tr>
                    <t t-if="true">
                        <q-td>1[]</q-td>
                        <q-td>2</q-td>
                    </t>
                    <t t-else="">
                        <q-td>3</q-td>
                        <q-td>4</q-td>
                    </t>
                </q-tr>
                <q-tr>
                    <q-td>5</q-td>
                    <q-td>6</q-td>
                </q-tr>
            </q-tbody>
        </q-table></div>`,
        getEditorOptions()
    );

    await hover(queryAll(":iframe q-th")[1]);
    await animationFrame();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(1);
    expect(".o-dropdown-item").toHaveCount(0);

    await contains(".o-overlay-container .o-we-table-menu").click();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(1);
    expect(".o-dropdown-item").toHaveCount(3);

    await hover(":iframe q-table");
    await animationFrame();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(1);
    expect(".o-dropdown-item").toHaveCount(3);

    await contains(":iframe q-table").click();
    await animationFrame();
    expect(".o-overlay-container .o-we-table-menu").toHaveCount(0);
    expect(".o-dropdown-item").toHaveCount(0);
});

test("push and remove readable expression as text node", async () => {
    const { editor, el } = await setupEditor(
        `<div>a<span t-field="doc.field" data-oe-expression-readable="human > expr"></span></div>`,
        getEditorOptions()
    );
    expect(getContent(el)).toBe(
        `<div class="o-paragraph">a<span t-field="doc.field" data-oe-expression-readable="human > expr" data-oe-protected="true" contenteditable="false">human > expr</span></div>`
    );
    expect(getContent(editor.getElContent())).toBe(
        '<div>a<span t-field="doc.field" data-oe-expression-readable="human > expr"></span></div>'
    );
});

test("field base path from oe-context", async () => {
    const oeContext = JSON.stringify({
        docs: {
            model: "some.model",
            name: "Some Model",
        },
        doc: {
            model: "some.model",
            name: "Some Model",
        },
    });

    const { editor, el } = await setupEditor(
        `<div oe-context='${oeContext}' ws-view-id="1" t-foreach="docs" t-as="doc">hop hop</div>`,
        getEditorOptions()
    );
    await setSelection({
        anchorNode: queryFirst(":iframe .odoo-editor-editable div"),
        anchorOffset: 0,
        focusOffset: 1,
    });
    await insertText(editor, "/");
    await contains(".o-we-powerbox .o-we-command-name:contains(/^Field$/)").click();
    await contains(".o-dynamic-field-popover .o_model_field_selector_value").click();
    await contains(".o_model_field_selector_popover_page li[data-name='field'] button").click();
    await contains(".o-dynamic-field-popover button.btn-primary").click();

    // Expect "doc.field" instead of "object.field"
    expect(getContent(el.querySelector("div"))).toBe(
        '<span data-oe-expression-readable="My little field" t-field="doc.field" data-oe-demo="My little field" data-oe-protected="true" contenteditable="false">My little field</span>[]'
    );
});

test("auto focus hintable", async () => {
    // a hintable is something matched by any hint registered in the plugins resources
    // that is a descendant of .page
    const oeContext = JSON.stringify({
        doc: {
            model: "some.model",
            name: "Some Model",
        },
    });

    const { el } = await setupEditor(
        `<div class="page" oe-context='${oeContext}' ws-view-id="1"><div class="oe_structure"></div></div>`,
        getEditorOptions()
    );
    await animationFrame();

    expect(document.activeElement).toBe(queryOne("iframe"));
    expect(getContent(el)).toBe(
        `<p data-selection-placeholder=""><br></p><div class="page" oe-context='${oeContext}' ws-view-id="1"><div class="oe_structure o-paragraph o-we-hint" o-we-hint-text='Type "/" for commands'>[]<br></div></div><p data-selection-placeholder=""><br></p>`
    );
});

test("/fields supported types", async () => {
    class Dummy0 extends models.Model {}
    class Dummy extends models.Model {
        properties = fields.Properties({ definition_record: "", definition_record_field: "" });
        dummy_name = fields.Text();
        m2o = fields.Many2one({ relation: Dummy0._name });
        o2m = fields.One2many({ relation: Dummy0._name });
        bool = fields.Boolean();
    }
    defineModels([Dummy, Dummy0]);
    const oeContext = JSON.stringify({
        doc: {
            model: Dummy._name,
            name: "Some Model",
            in_foreach: true,
        },
    });

    const { editor } = await setupEditor(
        `<div class="page" oe-context='${oeContext}' ws-view-id="1"><div class="oe_structure">[]</div></div>`,
        getEditorOptions()
    );
    await animationFrame();
    await insertText(editor, "/");
    await contains(".o-we-command:contains(Field)").click();

    await contains(".o_model_field_selector_value").click();
    await waitFor(".o_model_field_selector_popover");
    expect(
        queryAll(".o_model_field_selector_popover_page .o_model_field_selector_popover_item").map(
            (e) => e.textContent
        )
    ).toEqual(["Created on", "Display name", "Dummy name", "Id", "Last Modified on", "M2o", "O2m"]);
});

test("theme colors are not available", async () => {
    await setupEditor(`<div><span>some [text]</span></div>`, getEditorOptions());
    await contains(".o-we-toolbar .o-select-color-foreground").click();
    await contains(".solid-tab").click();
    expect(".o_colorpicker_section").toHaveInnerHTML("");
});

test("prevent selection placeholders in between header article footer", async () => {
    const { el } = await setupEditor(
        `
        <div class="header"><div /></div>
        <div class="article"><div /></div>
        <div class="footer"><div /></div>`,
        getEditorOptions()
    );
    expect(getContent(el)).toBe(`
        <div class="header"><div class="o-paragraph o-we-hint" o-we-hint-text='Type "/" for commands'>[]<br></div></div>
        <div class="article"><div class="o-paragraph"><br></div></div>
        <div class="footer"><div class="o-paragraph"><br></div></div>`);
});

test("do not add selection placeholder directly in article if report document exists", async () => {
    const { el } = await setupEditor(
        `<main>
            <t t-name="web.some_layout" ws-view-id="42">
                <div class="article">
                    <t ws-view-id="1" ws-call-key="1" ws-call-group-key="1">
                        <div />
                    </t>
                </div>
            </t>
        </main>`,
        getEditorOptions()
    );
    const article = el.querySelector(".article");
    const reportDocument = article.querySelector("[ws-view-id='1']");

    expect(article.children[0]).toBe(reportDocument);
    expect(reportDocument.querySelector(".o-paragraph")).not.toBe(null);
});
