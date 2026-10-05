import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { queryAllTexts } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    defineModels,
    fields,
    models,
    onRpc,
    serverState,
} from "@web/../tests/web_test_helpers";
import { pick } from "@web/core/utils/objects";
import { editView, mountViewEditor } from "../view_editor_tests_utils";

describe.current.tags("desktop");

defineMailModels();

class Partner extends models.Model {
    _name = "partner";
}

defineModels([Partner]);

test("empty search editor", async () => {
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `<search/>`,
    });

    expect(".o_web_studio_search_view_editor").toHaveCount(1);
    expect(".o-web-studio-search--fields .o_web_studio_hook").toHaveCount(1);
    expect(".o-web-studio-search--filters .o_web_studio_hook").toHaveCount(1);
    expect(".o-web-studio-search--groupbys .o_web_studio_hook").toHaveCount(1);
    expect(".o_web_studio_search_view_editor [data-studio-xpath]").toHaveCount(0);
});

test("search editor", async () => {
    expect.assertions(15);

    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `
            <search>
                <field name='display_name'/>
                <filter string='My Name'
                    name='my_name'
                    domain='[("display_name","=",Paul)]'
                />
                <group expand='0' string='Filters'>
                    <filter string='My Name2'
                        name='my_name2'
                        domain='[("display_name","=",Paul2)]'
                />
                </group>
                <group expand='0' string='Group By'>
                    <filter name='groupby_display_name'
                    domain='[]' context="{'group_by':'display_name'}"/>
                </group>
            </search>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        expect(params.operations[0].node.attrs).toEqual({ name: "display_name" });
    });

    expect(".o_web_studio_search_view_editor").toHaveCount(1);
    expect(".o-web-studio-search--fields .o_web_studio_hook").toHaveCount(2);
    expect(".o-web-studio-search--filters .o_web_studio_hook").toHaveCount(4);
    expect(".o-web-studio-search--groupbys .o_web_studio_hook").toHaveCount(2);
    expect(".o-web-studio-search--fields [data-studio-xpath]").toHaveCount(1);
    expect(".o-web-studio-search--filters [data-studio-xpath]").toHaveCount(2);
    expect(".o-web-studio-search--groupbys [data-studio-xpath]").toHaveCount(1);
    expect(".o_web_studio_search_view_editor [data-studio-xpath]").toHaveCount(4);

    await contains(
        ".o_web_studio_search_view_editor .o_web_studio_search_autocompletion_container [data-studio-xpath]"
    ).click();
    expect(".o_web_studio_sidebar .o_notebook .nav-link.active").toHaveText("Properties");
    expect(".o_web_studio_sidebar .o_web_studio_property input[name='label']").toHaveValue(
        "Display name"
    );
    expect(
        ".o_web_studio_search_view_editor .o_web_studio_search_autocompletion_container [data-studio-xpath]"
    ).toHaveClass(["o-web-studio-editor--element-clicked"]);

    await contains(".o_web_studio_sidebar .nav-link:nth-child(1)").click();
    expect(".o_web_studio_existing_fields > .o-draggable").toHaveCount(4);
    await contains(
        ".o_web_studio_existing_fields > .o-draggable.o_web_studio_field_char"
    ).dragAndDrop(".o-web-studio-search--fields .o_web_studio_hook:nth-child(1)");
    await animationFrame();
    expect.verifySteps(["edit_view"]);
    expect(".o_web_studio_existing_fields > .o-draggable").toHaveCount(4);
});

test("delete a field", async () => {
    expect.assertions(4);

    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `<search><field name='display_name'/></search>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        expect(params.operations[0]).toEqual({
            target: {
                attrs: { name: "display_name" },
                tag: "field",
                xpath_info: [
                    {
                        indice: 1,
                        tag: "search",
                    },
                    {
                        indice: 1,
                        tag: "field",
                    },
                ],
            },
            type: "remove",
        });
        return editView(params, "search", "<search />");
    });

    expect("[data-studio-xpath]").toHaveCount(1);
    await contains(".o_web_studio_search_autocompletion_container [data-studio-xpath]").click();
    await contains(".o_web_studio_sidebar .o_web_studio_remove").click();
    await contains(".modal footer .btn-primary").click();

    expect.verifySteps(["edit_view"]);
    expect("[data-studio-xpath]").toHaveCount(0);
});

test("indicate that regular stored field(except date/datetime) can not be dropped in 'Filters' section", async () => {
    Partner._fields.age = fields.Integer();
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `<search/>`,
    });

    const { cancel, moveTo } = await contains(
        ".o_web_studio_existing_fields .o-draggable.o_web_studio_field_integer:contains(Age)"
    ).drag();
    await moveTo(".o_web_studio_hook");
    expect(".o-web-studio-search--filters").toHaveClass(["o-web-studio-search--drop-disable"]);
    expect(".o-web-studio-search--groupbys").not.toHaveClass(["o-web-studio-search--drop-disable"]);
    expect(".o-web-studio-search--fields").not.toHaveClass(["o-web-studio-search--drop-disable"]);

    await cancel();
});

test("indicate that ungroupable field can not be dropped in 'Filters' and 'Group by' sections", async () => {
    Partner._fields.age = fields.Integer({ groupable: false });
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `<search/>`,
    });

    const { cancel, moveTo } = await contains(
        ".o_web_studio_existing_fields .o-draggable.o_web_studio_field_integer:contains(Age)"
    ).drag();
    await moveTo(".o_web_studio_hook");

    expect(".o-web-studio-search--groupbys").toHaveClass(["o-web-studio-search--drop-disable"]);
    expect(".o-web-studio-search--filters").toHaveClass(["o-web-studio-search--drop-disable"]);
    expect(".o-web-studio-search--fields").not.toHaveClass(["o-web-studio-search--drop-disable"]);

    await cancel();
});

test("many2many field can be dropped in 'Group by' sections", async () => {
    Partner._fields.message_ids = fields.Many2many({ relation: "mail.message" });
    const arch = `
        <search>
            <field name='display_name'/>
            <group expand='0' string='Group By'>
                <filter name='groupby_display_name' domain='[]' context="{'group_by':'display_name'}"/>
                <filter name='groupby_m2m' domain='[]' context="{'group_by':'m2m'}"/>
            </group>
        </search>`;

    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `
        <search>
            <field name='display_name'/>
            <group expand='0' string='Group By'>
                <filter name='groupby_display_name' domain='[]' context="{'group_by':'display_name'}"/>
            </group>
        </search>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        expect(params.operations[0].node.attrs.context).toBe("{'group_by': 'message_ids'}");
        return editView(params, "search", arch);
    });

    expect(".o-web-studio-search--groupbys [data-studio-xpath]").toHaveCount(1);
    await contains(".o_web_studio_existing_fields > .o_web_studio_field_many2many").dragAndDrop(
        ".o-web-studio-search--groupbys .o_web_studio_hook"
    );

    expect.verifySteps(["edit_view"]);
    expect(".o-web-studio-search--groupbys [data-studio-xpath]").toHaveCount(2);
});

test("existing field section should be unfolded by default in search", async () => {
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `<search><field name='display_name'/></search>`,
    });

    expect(".o_web_studio_existing_fields_header i").toHaveAttribute(
        "data-icon",
        "arrow_drop_down"
    );
    expect(".o_web_studio_existing_fields_section").toBeVisible();
});

test("indicate that separators can not be dropped in 'Automcompletion Fields' and 'Group by' sections", async () => {
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `<search/>`,
    });

    const { cancel, moveTo } = await contains(".o-draggable.o_web_studio_filter_separator").drag();
    await moveTo(".o_web_studio_hook");

    expect(".o-web-studio-search--groupbys").toHaveClass(["o-web-studio-search--drop-disable"]);
    expect(".o-web-studio-search--fields").toHaveClass(["o-web-studio-search--drop-disable"]);
    expect(".o-web-studio-search--filters").not.toHaveClass(["o-web-studio-search--drop-disable"]);

    await cancel();
});

test("indicate that filter can not be dropped in 'Automcompletion Fields' and 'Group by' sections", async () => {
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `<search/>`,
    });

    const { cancel, moveTo } = await contains(".o-draggable.o_web_studio_filter").drag();
    await moveTo(".o_web_studio_hook");

    expect(".o-web-studio-search--groupbys").toHaveClass(["o-web-studio-search--drop-disable"]);
    expect(".o-web-studio-search--fields").toHaveClass(["o-web-studio-search--drop-disable"]);
    expect(".o-web-studio-search--filters").not.toHaveClass(["o-web-studio-search--drop-disable"]);

    await cancel();
});

test("move a date/datetime field in search filter dropdown", async () => {
    expect.assertions(6);

    Partner._fields.start = fields.Datetime();

    const arch = `
        <search>
            <filter string='Start Date'
                name='start'
                date='start'
            />
        </search>`;

    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `<search/>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        expect(params.operations[0].node.tag).toBe("filter");
        expect(params.operations[0].node.attrs.date).toBe("start");
        return editView(params, "search", arch);
    });

    expect(
        ".o_web_studio_search_sub_item.o-web-studio-search--filters .o_web_studio_hook"
    ).toHaveCount(1);

    await contains(
        ".o_web_studio_existing_fields .o-draggable.o_web_studio_field_datetime:contains('Start')"
    ).dragAndDrop(".o_web_studio_search_sub_item.o-web-studio-search--filters .o_web_studio_hook");

    expect.verifySteps(["edit_view"]);

    expect(
        ".o_web_studio_search_sub_item.o-web-studio-search--filters .o_web_studio_hook"
    ).toHaveCount(2);
    expect(
        ".o_web_studio_search_sub_item.o-web-studio-search--filters [data-studio-xpath]"
    ).toHaveCount(1);
});

test("set an end date on a date filter", async () => {
    Partner._fields.start = fields.Datetime({ string: "Start" });
    Partner._fields.stop = fields.Datetime({ string: "Stop" });
    Partner._fields.deadline = fields.Date({ string: "Deadline" });
    Partner._fields.duration = fields.Date({ string: "Duration", searchable: false });

    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `
            <search>
                <filter string='Period' name='period' date='start'/>
            </search>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        expect(params.operations[0].new_attrs).toEqual({ end_date: "stop" });
    });

    await contains(".o-web-studio-search--filters .o-web-studio-editor--element-clickable").click();
    await contains(".o_web_studio_property_end_date .o_select_menu_toggler").click();

    // the date fields the records can be searched on, but the one the filter starts from
    expect(queryAllTexts(".o_select_menu_item").sort()).toEqual([
        "Created on",
        "Deadline",
        "Last Modified on",
        "Stop",
    ]);

    await contains(".o_select_menu_item:contains(Stop)").click();
    expect.verifySteps(["edit_view"]);
});

test("filters that are not date filters have no end date", async () => {
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `
            <search>
                <filter string='My Filter' name='my_name' domain='[("display_name","=",Woof)]'/>
            </search>`,
    });

    await contains(".o-web-studio-search--filters .o-web-studio-editor--element-clickable").click();
    expect(".o_web_studio_property_domain").toHaveCount(1);
    expect(".o_web_studio_property_end_date").toHaveCount(0);
});

test("empty search editor: drag a groupby", async () => {
    expect.assertions(4);

    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `<search/>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        expect(pick(params.operations[0].node.attrs, "context", "create_group", "string")).toEqual({
            string: "Last Modified on",
            context: "{'group_by': 'write_date'}",
            create_group: true,
        });
        const arch = `<search>
                <group name="studio_group_by">
                    <filter name="studio_group_by_abcdef" string="Last Updated on" context="{'group_by': 'write_date'}" />
                </group>
            </search>`;
        return editView(params, "search", arch);
    });

    await contains(
        `.o_web_studio_sidebar .o_web_studio_existing_fields > .o-draggable[data-drop='${JSON.stringify(
            { fieldName: "write_date" }
        )}']`
    ).dragAndDrop(".o_web_studio_view_renderer .o-web-studio-search--groupbys .o_web_studio_hook");

    expect.verifySteps(["edit_view"]);

    expect(".o-web-studio-search--groupbys .o-web-studio-editor--element-clickable").toHaveCount(1);
    expect(".o-web-studio-search--groupbys .o-web-studio-editor--element-clickable").toHaveText(
        "Last Updated on"
    );
});

test("integer field can be dropped in 'Group by' sections", async () => {
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `<search/>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        expect(params.operations[0].node.attrs.context).toBe("{'group_by': 'id'}");
        const arch = `<search>
                <group expand='0' string='Group By'>
                    <filter name='groupby_id' domain='[]' context="{'group_by':'id'}"/>
                </group>
            </search>`;
        return editView(params, "search", arch);
    });

    expect(".o-web-studio-search--groupbys [data-studio-xpath]").toHaveCount(0);

    await contains(".o_web_studio_existing_fields > .o_web_studio_field_integer").dragAndDrop(
        ".o-web-studio-search--groupbys .o_web_studio_hook"
    );

    expect.verifySteps(["edit_view"]);
    expect(".o-web-studio-search--groupbys [data-studio-xpath]").toHaveCount(1);
});

test("check invisible modifiers properties", async () => {
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `
            <search>
                <field name='display_name'/>
                <filter string='My Filter'
                    name='my_name'
                    domain='[("display_name","=",Woof)]'
                />
                <group expand='0' string='Group By'>
                    <filter string="My Groupby" name='groupby_display_name'
                    domain='[]' context="{'group_by':'display_name'}"/>
                </group>
            </search>`,
    });

    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        expect(params.operations[0].new_attrs).toEqual({ invisible: "True" });
    });

    // Filter
    await contains(".o-web-studio-search--filters .o-web-studio-editor--element-clickable").click();
    expect(".o_web_studio_sidebar input[name='invisible']").toBeVisible();
    expect(".o_web_studio_sidebar input[name='label']").toHaveValue("My Filter");
    expect(".o_web_studio_sidebar input[name='domain']").toHaveValue('[("display_name","=",Woof)]');

    await contains(".o_web_studio_sidebar input[name='invisible']").click();
    expect.verifySteps(["edit_view"]);

    // GroupBy
    await contains(
        ".o-web-studio-search--groupbys .o-web-studio-editor--element-clickable"
    ).click();
    expect(".o_web_studio_sidebar input[name='invisible']").toBeVisible();
    expect(".o_web_studio_sidebar input[name='label']").toHaveValue("My Groupby");

    await contains(".o_web_studio_sidebar input[name='invisible']").click();
    expect.verifySteps(["edit_view"]);
});

test("invisible fields are made visible with hatched bg", async () => {
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `
            <search>
                <field name='display_name'/>
                <filter string='You can see me'
                    name='my_name'
                    domain='[("display_name","=",Woof)]'
                />
                <filter string='You cannot see me'
                    name='my_name'
                    invisible='true'
                    domain='[("display_name","=",Woof)]'
                />
            </search>`,
    });
    expect(".o-web-studio-search--filters .o-web-studio-editor--element-clickable").toHaveCount(1);
    await contains(".o_web_studio_sidebar .o_notebook_headers .nav-link:contains(View)").click();
    await contains(".o_web_studio_sidebar #show_invisible").click();
    expect(".o-web-studio-search--filters .o-web-studio-editor--element-clickable").toHaveCount(2);
    expect(".o-web-studio-search--filters .o_web_studio_show_invisible").toHaveCount(1);
});

test("check modifiers simple dialog", async () => {
    // The expression is in readonly if not in debug mode
    serverState.debug = "1";
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `
            <search>
                <field name='display_name'/>
                <filter string='My Filter'
                    name='my_name'
                    domain='[("display_name","=",Woof)]'
                />
            </search>`,
    });
    onRpc("/web_studio/edit_view", async (request) => {
        expect.step("edit_view");
        const { params } = await request.json();
        expect(params.operations[0].new_attrs).toEqual({ invisible: "True" });
    });
    await contains(".o-web-studio-search--filters .o-web-studio-editor--element-clickable").click();
    await contains(".o_web_studio_sidebar a[role='button']").click();
    expect(".o_dialog h4").toHaveText("Edit Condition");

    // '1' should be evaluated to 'True'
    await contains(".o_dialog main input").edit("1");

    await contains(".o_dialog footer button:first-child").click();
    expect.verifySteps(["edit_view"]);
});

test("autocompletion container does not contain the searchpanel fields", async () => {
    Partner._fields.age = fields.Integer();
    await mountViewEditor({
        type: "search",
        resModel: "partner",
        arch: `
        <search>
            <field name='display_name'/>
            <searchpanel>
                <field name='age'/>
            </searchpanel>
        </search>`,
    });

    expect(
        ".o_web_studio_search_autocompletion_container .o-web-studio-editor--element-clickable"
    ).toHaveCount(1);
    expect(
        ".o_web_studio_search_autocompletion_container .o-web-studio-editor--element-clickable"
    ).toHaveText("Display name");
});
