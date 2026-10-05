/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import { allowTranslations } from "@web/../tests/web_test_helpers";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

import { CallFlowField } from "@voip/call_flow/call_flow_field";
import { FlowNodeConfigurationDialog } from "@voip/flow_editor/flow_node_configuration_dialog";
import { RECORD_CONFIGS } from "@voip/flow_editor/node_types/terminal_record_flow_node";

test.tags("headless");

function configuredNode() {
    return {
        id: "queue",
        type: "queue",
        position: { x: 10, y: 20 },
        size: { width: 200, height: 300 },
        record: {
            resModel: "voip.queue",
            resId: 1,
            data: { display_name: "Queue" },
        },
        input: { id: "input", direction: "input", accepts: ["flow"] },
        outputs: [
            {
                id: "busy",
                direction: "output",
                provides: "flow",
                maxConnections: 1,
            },
        ],
        data: { label: "Queue", manuallyResized: true },
    };
}

function setupDialog(node, callbacks = {}) {
    const context = {
        env: { dialogData: {} },
        props: {
            close: callbacks.close || (() => {}),
            node,
            onApply: callbacks.onApply || (() => true),
            onCancel: callbacks.onCancel || (() => {}),
        },
    };
    FlowNodeConfigurationDialog.prototype.setup.call(context);
    return context;
}

describe("FlowNodeConfigurationDialog", () => {
    test("edits an isolated copy of every mutable node value", () => {
        const node = configuredNode();
        const dialog = setupDialog(node);

        dialog.draft.position.x = 100;
        dialog.draft.size.height = 500;
        dialog.draft.record.data.display_name = "Other queue";
        dialog.draft.input.id = "other-input";
        dialog.draft.outputs[0].id = "no_answer";
        dialog.draft.data.manuallyResized = false;

        expect(node).toEqual(configuredNode());
    });

    test("Apply propagates the draft and closes only when accepted", async () => {
        const appliedDrafts = [];
        let closeCount = 0;
        const dialog = setupDialog(configuredNode(), {
            close: () => closeCount++,
            onApply: (draft) => {
                appliedDrafts.push(draft);
                return appliedDrafts.length > 1;
            },
        });

        await FlowNodeConfigurationDialog.prototype.apply.call(dialog);
        expect(closeCount).toBe(0);
        await FlowNodeConfigurationDialog.prototype.apply.call(dialog);
        expect(appliedDrafts).toEqual([dialog.draft, dialog.draft]);
        expect(closeCount).toBe(1);
    });

    test("Cancel discards the draft and closes the dialog", () => {
        const node = configuredNode();
        let cancelCount = 0;
        let closeCount = 0;
        const dialog = setupDialog(node, {
            close: () => closeCount++,
            onCancel: () => cancelCount++,
        });
        dialog.draft.size.height = 500;

        FlowNodeConfigurationDialog.prototype.cancel.call(dialog);

        expect(node.size.height).toBe(300);
        expect(cancelCount).toBe(1);
        expect(closeCount).toBe(1);
    });

    test("the secondary action is labelled Discard", () => {
        allowTranslations();
        const dialog = setupDialog(configuredNode());
        const getCancelLabel = Object.getOwnPropertyDescriptor(
            FlowNodeConfigurationDialog.prototype,
            "cancelLabel"
        ).get;

        expect(getCancelLabel.call(dialog)).toBe("Discard");
    });
});

describe("CallFlowField node configuration", () => {
    test("record nodes open their search dialog directly", () => {
        for (const [type, config] of Object.entries(RECORD_CONFIGS)) {
            let dialogCall;
            const field = {
                dialog: {
                    add(component, props, options) {
                        dialogCall = { component, options, props };
                    },
                },
                state: { nodes: [] },
                updateRecord() {},
            };
            const node = {
                id: type,
                type,
                position: { x: 0, y: 0 },
                size: { width: 200, height: 120 },
                outputs: [],
                data: {},
            };

            CallFlowField.prototype.configureNode.call(field, node);

            expect(dialogCall.component).toBe(SelectCreateDialog);
            // A node's own record (e.g. the Menu behind "Play Audio") can
            // differ from what its picker searches/creates (e.g. a Sound).
            expect(dialogCall.props.resModel).toBe(config.pickerResModel || config.resModel);
            expect(dialogCall.props.domain).toEqual(config.domain || []);
            expect(dialogCall.props.context).toEqual(config.context || {});
            expect(dialogCall.props.multiSelect).toBe(false);
        }
    });

    test("selecting a record applies it to the node", async () => {
        let dialogProps;
        let appliedNode;
        const node = {
            id: "contact",
            type: "contact",
            position: { x: 0, y: 0 },
            size: { width: 200, height: 120 },
            outputs: [],
            data: {},
        };
        const field = {
            applyNodeConfiguration(configuredNode) {
                appliedNode = configuredNode;
                return true;
            },
            dialog: {
                add(component, props) {
                    expect(component).toBe(SelectCreateDialog);
                    dialogProps = props;
                },
            },
            orm: {
                read() {
                    return [{ id: 7, display_name: "Ada Lovelace" }];
                },
            },
            state: { nodes: [node] },
            updateRecord() {},
        };

        CallFlowField.prototype.configureNode.call(field, node);
        await dialogProps.onSelected([7]);

        expect(appliedNode.record).toEqual({
            resModel: "res.partner",
            resId: 7,
            data: { id: 7, display_name: "Ada Lovelace" },
        });
    });

    test("creating a record opens its form from the search dialog", () => {
        const dialogCalls = [];
        const node = {
            id: "audio_message",
            type: "audio_message",
            position: { x: 0, y: 0 },
            size: { width: 200, height: 120 },
            outputs: [],
            data: {},
        };
        const field = {
            dialog: {
                add(component, props, options) {
                    dialogCalls.push({ component, options, props });
                },
            },
            state: { nodes: [node] },
            updateRecord() {},
        };

        CallFlowField.prototype.configureNode.call(field, node, { removeOnCancel: true });
        dialogCalls[0].props.onCreateEdit();
        dialogCalls[0].options.onClose();

        expect(dialogCalls[1].component).toBe(FormViewDialog);
        expect(dialogCalls[1].props.resModel).toBe("voip.sound");
        expect(dialogCalls[1].props.context.voip_call_flow_audio_creation).toBe(true);
        expect(RECORD_CONFIGS.ivr.context.voip_call_flow_audio_creation).toBe(true);
        expect(field.state.nodes).toEqual([node]);
    });

    test("closing the search dialog removes a freshly added node", () => {
        let dialogOptions;
        let updateCount = 0;
        const node = {
            id: "contact",
            type: "contact",
            position: { x: 0, y: 0 },
            size: { width: 200, height: 120 },
            outputs: [],
            data: {},
        };
        const field = {
            dialog: {
                add(_component, _props, options) {
                    dialogOptions = options;
                },
            },
            state: { nodes: [node] },
            updateRecord: () => updateCount++,
        };

        CallFlowField.prototype.configureNode.call(field, node, { removeOnCancel: true });
        dialogOptions.onClose();

        expect(field.state.nodes).toEqual([]);
        expect(updateCount).toBe(1);
    });

    test("Cancel removes a freshly dropped node only", () => {
        const existingNode = { id: "existing" };
        const newNode = { id: "new" };
        let dialogProps;
        let updateCount = 0;
        const field = {
            dialog: {
                add(component, props) {
                    expect(component).toBe(FlowNodeConfigurationDialog);
                    dialogProps = props;
                },
            },
            registry: { getNodeConfiguration: () => ({}) },
            state: { nodes: [existingNode, newNode] },
            updateRecord: () => updateCount++,
        };

        CallFlowField.prototype.configureNode.call(field, existingNode);
        dialogProps.onCancel();
        expect(field.state.nodes).toEqual([existingNode, newNode]);
        expect(updateCount).toBe(0);

        CallFlowField.prototype.configureNode.call(field, newNode, { removeOnCancel: true });
        dialogProps.onCancel();
        expect(field.state.nodes).toEqual([existingNode]);
        expect(updateCount).toBe(1);
    });

    test("Apply stores an isolated copy and removes obsolete connections", async () => {
        const original = configuredNode();
        const configured = configuredNode();
        configured.size.height = 400;
        configured.outputs = [];
        let updateCount = 0;
        const field = {
            notification: { add() {} },
            registry: { get: () => ({ validate: () => true }) },
            state: {
                nodes: [original],
                connections: [
                    {
                        id: "busy",
                        sourceNodeId: original.id,
                        sourcePortId: "busy",
                        targetNodeId: "target",
                        targetPortId: "input",
                    },
                ],
            },
            updateRecord: async () => updateCount++,
        };

        expect(await CallFlowField.prototype.applyNodeConfiguration.call(field, configured)).toBe(
            true
        );
        expect(field.state.nodes[0]).toEqual(configured);
        expect(field.state.connections).toEqual([]);
        expect(updateCount).toBe(1);

        configured.position.x = 999;
        configured.size.height = 999;
        configured.record.data.display_name = "Changed";
        configured.outputs.push({ id: "other" });
        configured.data.manuallyResized = false;
        expect(field.state.nodes[0].position.x).toBe(10);
        expect(field.state.nodes[0].size.height).toBe(400);
        expect(field.state.nodes[0].record.data.display_name).toBe("Queue");
        expect(field.state.nodes[0].outputs).toEqual([]);
        expect(field.state.nodes[0].data.manuallyResized).toBe(true);
    });
});
