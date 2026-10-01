import { expect, test } from "@odoo/hoot";

import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { PbxForwardDestinationRefField } from "@voip/views/fields/pbx_forward_destination_field";
import {
    contains,
    defineModels,
    editSelectMenu,
    fields,
    models,
    mountView,
    pagerNext,
} from "@web/../tests/web_test_helpers";

class User extends models.Model {
    _name = "voip.test.user";

    destination_kind = fields.Selection({
        selection: [
            ["test.call.group", "Group"],
            ["test.queue", "Queue"],
        ],
    });
    destination_ref = fields.Reference({
        selection: [
            ["test.call.group", "Group"],
            ["test.queue", "Queue"],
        ],
    });

    _records = [
        {
            id: 1,
            destination_kind: "test.call.group",
            destination_ref: "test.call.group,1",
        },
        {
            id: 2,
            destination_kind: "test.queue",
            destination_ref: "test.queue,1",
        },
    ];
}

class VoipCallGroup extends models.Model {
    _name = "test.call.group";

    name = fields.Char();

    _records = [{ id: 1, name: "Sales group" }];
}

class VoipQueue extends models.Model {
    _name = "test.queue";

    name = fields.Char();

    _records = [{ id: 1, name: "Support queue" }];
}

defineMailModels();
defineModels([User, VoipCallGroup, VoipQueue]);

const formArch = /* xml */ `
    <form>
        <field name="destination_kind"/>
        <field name="destination_ref" widget="voip_pbx_forward_destination_ref" options="{'kind_field': 'destination_kind'}"/>
    </form>`;

test("switching destination kind writes the reference with the new model", () => {
    let destination;
    PbxForwardDestinationRefField.prototype.updateM2O.call(
        {
            // Simulate the relation cached by ReferenceField for the existing destination.
            state: { currentRelation: "voip.call.group" },
            getRelation: () => "voip.queue",
            props: {
                name: "destination_ref",
                record: {
                    update(values) {
                        destination = values.destination_ref;
                    },
                },
            },
        },
        { id: 1, display_name: "Support queue" }
    );

    expect(destination).toEqual({
        displayName: "Support queue",
        resId: 1,
        resModel: "voip.queue",
    });
});

test("discarding a destination kind change restores the reference", async () => {
    await mountView({
        type: "form",
        resModel: "voip.test.user",
        resId: 1,
        arch: formArch,
    });

    expect(".o_field_widget[name=destination_ref] input").toHaveValue("Sales group");
    await editSelectMenu(".o_field_widget[name=destination_kind] input", { value: "Queue" });
    expect(".o_field_widget[name=destination_ref] input").toHaveValue("");

    await contains(".o_form_button_cancel").click();
    expect(".o_field_widget[name=destination_ref] input").toHaveValue("Sales group");
    expect(".o_form_status_indicator_buttons").toHaveClass("invisible");
});

test("navigating to a record with another destination kind preserves its reference", async () => {
    await mountView({
        type: "form",
        resModel: "voip.test.user",
        resId: 1,
        resIds: [1, 2],
        arch: formArch,
    });

    await pagerNext();
    expect(".o_field_widget[name=destination_ref] input").toHaveValue("Support queue");
    expect(".o_form_status_indicator_buttons").toHaveClass("invisible");
});
