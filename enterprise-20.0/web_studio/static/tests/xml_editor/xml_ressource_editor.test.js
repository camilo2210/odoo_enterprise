import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { queryOne } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { Component, signal, xml } from "@odoo/owl";
import { contains, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { XmlResourceEditor } from "@web_studio/client_action/xml_resource_editor/xml_resource_editor";

describe.current.tags("desktop");

defineMailModels();

test("can display warnings", async () => {
    onRpc("/web_studio/get_xml_editor_resources", async () => ({
        views: [
            {
                id: 1,
                arch: "<data/>",
            },
        ],
    }));

    class Parent extends Component {
        static components = { XmlResourceEditor };
        static template = xml`<XmlResourceEditor displayAlerts="this.displayAlerts()" onClose="() => {}" mainResourceId="1" />`;
        displayAlerts = displayAlerts;
    }

    const displayAlerts = signal(true);
    await mountWithCleanup(Parent);
    await animationFrame();
    expect(".o_web_studio_code_editor_info .alert.alert-warning").toHaveCount(1);
    displayAlerts.set(false);
    await animationFrame();
    expect(".o_web_studio_code_editor_info .alert.alert-warning").toHaveCount(0);
});

test("stores and restores the cursor position when reloading resources after save", async () => {
    let arch = "<data>1\n2\n3\n4\n5\n</data>";
    onRpc("/web_studio/get_xml_editor_resources", () => {
        expect.step("load sources");
        return {
            views: [
                {
                    id: 1,
                    arch,
                },
            ],
        };
    });

    class Parent extends Component {
        static components = { XmlResourceEditor };
        static template = xml`<XmlResourceEditor onClose="() => {}" mainResourceId="1" onSave.bind="this.onSave" onCodeChange="() => {}"/>`;

        async onSave({ newCode }) {
            await Promise.resolve();
            arch = newCode;
        }
    }
    await mountWithCleanup(Parent);
    expect.verifySteps(["load sources"]);

    const aceEl = queryOne(".o_web_studio_code_editor.ace_editor");
    const editor = window.ace.edit(aceEl);
    expect(editor.getCursorPosition()).toEqual({
        column: 0,
        row: 0,
    });
    editor.selection.moveToPosition({
        row: 3,
        column: 1,
    });
    editor.insert("appended");
    await animationFrame();

    await contains(".o_web_studio_xml_resource_selector .btn-primary").click();
    await animationFrame();
    expect.verifySteps(["load sources"]);

    const newAceEl = queryOne(".o_web_studio_code_editor.ace_editor");
    const newEditor = window.ace.edit(newAceEl);
    expect(newEditor.getCursorPosition()).toEqual({
        column: 9,
        row: 3,
    });
});
