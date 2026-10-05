import { mailModels } from "@mail/../tests/mail_test_helpers";
import { expect, test } from "@odoo/hoot";
import { click, select, waitFor } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
    serverState,
} from "@web/../tests/web_test_helpers";

class TestRoute extends models.Model {
    destination_ref = fields.Reference({
        selection: [
            ["voip.call.flow", "Call Flow"],
            ["voip.extension", "Extension"],
            ["voip.call.group", "Group"],
            ["voip.ivr", "Menu"],
            ["voip.queue", "Queue"],
            ["voip.sound", "Sound"],
            ["res.users", "User"],
            ["res.partner", "Contact"],
            ["voip.voicemail", "Voice Mailbox"],
        ],
    });

    _records = [{ id: 1 }];
}

class NamedDestination extends models.Model {
    name = fields.Char();

    _records = [{ id: 1, name: "First destination" }];
    _views = {
        kanban: `<kanban><templates><t t-name="card"><field name="name"/></t></templates></kanban>`,
    };
}

class VoipCallFlow extends NamedDestination {
    _name = "voip.call.flow";
}
class VoipExtension extends NamedDestination {
    _name = "voip.extension";
}
class VoipCallGroup extends NamedDestination {
    _name = "voip.call.group";
}
class VoipIvr extends NamedDestination {
    _name = "voip.ivr";
}
class VoipQueue extends NamedDestination {
    _name = "voip.queue";
}
class VoipSound extends NamedDestination {
    _name = "voip.sound";
}
class VoipVoicemail extends NamedDestination {
    _name = "voip.voicemail";
}
defineModels({
    ...mailModels,
    TestRoute,
    VoipCallFlow,
    VoipExtension,
    VoipCallGroup,
    VoipIvr,
    VoipQueue,
    VoipSound,
    VoipVoicemail,
});

test("selecting a destination type selects its first record", async () => {
    await mountView({
        type: "form",
        resModel: "test.route",
        resId: 1,
        arch: `<form><field name="destination_ref" widget="voip_extension_destination"/></form>`,
    });

    await click("[name=destination_ref] select");
    await select("voip.queue");
    await animationFrame();

    expect("[name=destination_ref] input").toHaveValue("First destination");
    expect("[name=destination_ref] [data-icon=headphones]").toHaveAttribute("title", "Queue");
    expect("[name=destination_ref] select").toHaveClass("w-25");
    expect("[name=destination_ref] > div > div.flex-grow-1").toHaveCount(1);
});

test("rapid destination type changes only load the latest relation", async () => {
    onRpc("search_read", ({ model }) => expect.step(model));
    await mountView({
        type: "form",
        resModel: "test.route",
        resId: 1,
        arch: `<form><field name="destination_ref" widget="voip_extension_destination"/></form>`,
    });

    await click("[name=destination_ref] select");
    const firstSelection = select("voip.queue");
    const secondSelection = select("res.users");
    await Promise.all([firstSelection, secondSelection]);
    await animationFrame();

    expect.verifySteps(["res.users"]);
    expect("[name=destination_ref] select").toHaveValue("res.users");
});

test.tags("desktop");
test("clearing a destination target keeps its selected type invalid", async () => {
    await mountView({
        type: "form",
        resModel: "test.route",
        resId: 1,
        arch: `<form><field name="destination_ref" widget="voip_extension_destination"/></form>`,
    });

    await click("[name=destination_ref] select");
    await select("voip.queue");
    await waitFor("[name=destination_ref] input:value(First destination)");
    await contains("[name=destination_ref] input").clear({ confirm: "blur" });
    await contains(".o_form_button_save").click();
    await animationFrame();

    expect("[name=destination_ref]").toHaveClass("o_field_invalid");
});

test.tags("mobile");
test("clearing a destination target from the selection dialog keeps its type invalid", async () => {
    await mountView({
        type: "form",
        resModel: "test.route",
        resId: 1,
        arch: `<form><field name="destination_ref" widget="voip_extension_destination"/></form>`,
    });

    await click("[name=destination_ref] select");
    await select("voip.queue");
    await waitFor("[name=destination_ref] input:value(First destination)");
    await click("[name=destination_ref] input");
    await contains(".o_clear_button").click();
    await contains(".o_form_button_save").click();
    await animationFrame();

    expect("[name=destination_ref]").toHaveClass("o_field_invalid");
});

test("a destination type without targets stays invalid", async () => {
    VoipQueue._records = [];
    await mountView({
        type: "form",
        resModel: "test.route",
        resId: 1,
        arch: `<form><field name="destination_ref" widget="voip_extension_destination"/></form>`,
    });

    await click("[name=destination_ref] select");
    await select("voip.queue");
    await waitFor("[name=destination_ref].o_field_invalid");
    await contains(".o_form_button_save").click();
    await animationFrame();

    expect("[name=destination_ref]").toHaveClass("o_field_invalid");
});

test("all destination types have an icon or avatar", async () => {
    const records = [
        "voip.call.flow,1",
        "voip.extension,1",
        "voip.call.group,1",
        "voip.ivr,1",
        "voip.queue,1",
        "voip.sound,1",
        `res.users,${serverState.userId}`,
        `res.partner,${serverState.partnerId}`,
        "voip.voicemail,1",
    ].map((reference, index) => ({ id: index + 1, destination_ref: reference }));
    TestRoute._records = records;

    await mountView({
        type: "list",
        resModel: "test.route",
        arch: `<list><field name="destination_ref" widget="voip_extension_destination"/></list>`,
    });

    expect("[name=destination_ref] [role=img]").toHaveCount(7);
    expect("[name=destination_ref] .o_m2o_avatar img").toHaveCount(2);
    expect("[name=destination_ref] [title='Voice Mailbox']").toHaveAttribute("data-icon", "inbox");
    expect("[name=destination_ref] [title='Call Flow']").toHaveAttribute(
        "data-icon",
        "account_tree"
    );
    expect("[name=destination_ref] [title='Menu']").toHaveAttribute(
        "data-icon",
        "format_list_numbered"
    );
});
