import {
    animationFrame,
    describe,
    expect,
    hover,
    mockDate,
    queryFirst,
    runAllTimers,
    test,
} from "@odoo/hoot";
import {
    contains,
    defineModels,
    fields,
    findComponent,
    models,
    mountView,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { GridController } from "@web_grid/views/grid_controller";

class Grid extends models.Model {
    foo_id = fields.Many2one({ string: "Foo", relation: "foo" });
    date = fields.Date({ string: "Date" });
    time = fields.Float({
        string: "Float time field",
        digits: [2, 1],
        aggregator: "sum",
    });

    _records = [{ id: 1, date: "2023-03-20", foo_id: 1, time: 9.1 }];

    _views = {
        grid: `<grid editable="1">
                    <field name="foo_id" type="row"/>
                    <field name="date" type="col">
                        <range name="day" string="Day" span="day" step="day"/>
                    </field>
                    <field name="time" type="measure" widget="float_time"/>
                </grid>`,
    };
}

class Foo extends models.Model {
    name = fields.Char();

    _records = [{ name: "Foo" }];
}

defineModels([Grid, Foo]);
onRpc("grid_unavailability", () => ({}));

describe.current.tags("desktop");

test("FloatTimeGridCell in grid view", async () => {
    mockDate("2023-03-20 00:00:00");
    await mountView({
        type: "grid",
        resModel: "grid",
    });
    await hover(queryFirst(".o_grid_row .o_grid_cell_readonly"));
    await runAllTimers();
    expect(".o_grid_cell").toHaveCount(1, { message: "The component should be mounted" });
    await animationFrame();
    expect(".o_grid_cell span").toHaveCount(1, {
        message: "The component should be readonly once it is mounted",
    });
    expect(".o_grid_cell input").toHaveCount(0, {
        message: "No input should be displayed in the component since it is readonly.",
    });
    expect(".o_grid_cell").toHaveText("9h 6m", {
        message: "The component should have the value correctly formatted",
    });
    await contains(".o_grid_cell").click();
    await animationFrame();
    expect(".o_grid_cell input").toHaveCount(1, {
        message: "The component should be in edit mode.",
    });
    expect(".o_grid_cell input").toHaveAttribute("inputmode", "text");
    expect(".o_grid_cell span").toHaveCount(0, {
        message: "The component should no longer be in readonly mode.",
    });
    await contains(".o_grid_cell input").edit("9:30");
    expect(".o_grid_cell_readonly").toHaveText("9h 30m", {
        message: "The edition should be taken into account.",
    });
    expect(".o_grid_component[name='foo_id'] .o_form_uri").toHaveAttribute("href", "/odoo/m-foo/1");
});

test("patch of a hovered cell whose row was rebuilt away does not crash", async () => {
    // The steps below reproduce that a flakiness in a useLayoutEffect refactor:
    // hover a cell (overlay mounts, getCell resolves), then drop that row from
    // flakiness model and force a re-render WITHOUT moving the mouse (so the debounced
    // mouse-out never clears the cell signal). The re-render patches the overlay
    // and re-runs updateGridCell against the now-missing cell.

    mockDate("2023-03-20 00:00:00");

    const view = await mountView({
        type: "grid",
        resModel: "grid",
    });

    /** @type {GridController} */
    const { model } = findComponent(view, (comp) => comp instanceof GridController);

    await hover(queryFirst(".o_grid_row .o_grid_cell_readonly"));
    await runAllTimers();
    expect(".o_grid_cell").toHaveCount(1, {
        message: "The GridCell overlay should be mounted on the hovered cell",
    });

    // Emulate a reload that rebuilt the data without the hovered row: remove it
    // from the model so getCell() no longer resolves the stale element.
    delete model.data.rows["1"];
    await model.reload();
    await animationFrame();

    // Reaching this assertion proves the onPatched run did not throw.
    expect(".o_grid_cell").toHaveCount(1, {
        message: "The overlay survived the patch on a rebuilt-away cell",
    });
});
