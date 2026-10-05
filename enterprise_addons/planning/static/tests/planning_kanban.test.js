import { expect, test, beforeEach, describe, getFixture } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { mockDate } from "@odoo/hoot-mock";
import { contains } from "@mail/../tests/mail_test_helpers";
import { onRpc, mountWithCleanup, getService, defineActions } from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

import { definePlanningModels, planningModels, PlanningRole } from "./planning_mock_models";
import { resourceModels } from "@resource/../tests/resource_test_helpers";

describe.current.tags("desktop");

class PlanningSlot extends planningModels.PlanningSlot {
    _views = {
        kanban: `<kanban js_class="planning_kanban">
                    <field name="name"/>
                    <field name="repeat" invisible="1"/>
                    <templates>
                        <t t-name="menu">
                            <t t-if="widget.editable"><a role="menuitem" type="edit" class="dropdown-item">Edit</a></t>
                            <t t-if="widget.deletable"><a role="menuitem" type="delete" class="dropdown-item">Delete</a></t>
                        </t>
                        <t t-name="card">
                            <div>
                                <field name="name"/>
                            </div>
                        </t>
                    </templates>
                </kanban>`,
    };
}

planningModels.PlanningSlot = PlanningSlot;

definePlanningModels();
defineActions([
    {
        id: 1,
        name: "planning action",
        res_model: "planning.slot",
        type: "ir.actions.act_window",
        views: [[false, "kanban"]],
    },
]);

let target;

beforeEach(() => {
    PlanningSlot._records = [
        {
            id: 1,
            name: "First Record",
            start_datetime: "2019-03-11 08:00:00",
            end_datetime: "2019-03-11 12:00:00",
            resource_ids: [1],
            color: 7,
            role_id: 1,
            state: "1_draft",
            repeat: true,
        },
        {
            id: 2,
            name: "Second Record",
            start_datetime: "2019-03-13 08:00:00",
            end_datetime: "2019-03-13 12:00:00",
            resource_ids: [2],
            color: 9,
            role_id: 2,
            state: "2_published",
        },
    ];
    resourceModels.ResourceResource._records = [
        { id: 1, name: "Chaganlal" },
        { id: 2, name: "Maganlal" },
    ];
    PlanningRole._records = [
        { id: 1, name: "JavaScript Developer", color: 1 },
        { id: 2, name: "Functional Consultant", color: 2 },
    ];

    onRpc("check_access_rights", () => {
        return true;
    });

    mockDate("2019-03-13 00:00:00", +1);
    target = getFixture();
});

test("Display modal to choose recurrence type when deleting recurrent task", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await click(".o_kanban_record:contains('First Record') i[data-icon='more_vert']");
    await contains("a.dropdown-item", { count: 2 });
    await click("a.dropdown-item.oe_kanban_action");

    await contains("h4.modal-title");
    expect(target.querySelector("h4.modal-title")).toHaveText("Delete Recurring Shift");
});

test("Display confirm delete modal when deleting non recurrent task", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    await click(".o_kanban_record:contains('Second Record') i[data-icon='more_vert']");
    await contains("a.dropdown-item", { count: 2 });
    await click("a.dropdown-item.oe_kanban_action");

    await contains("h4.modal-title");
    expect(target.querySelector("h4.modal-title")).toHaveText("Bye-bye, record!");
});
