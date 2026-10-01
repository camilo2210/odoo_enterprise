/** @odoo-module **/

import { mailModels } from "@mail/../tests/mail_test_helpers";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import { proxy } from "@odoo/owl";
import {
    allowTranslations,
    clickCancel,
    clickSave,
    contains,
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { CallFlowField } from "@voip/call_flow/call_flow_field";

beforeEach(() => {
    allowTranslations();
});

class VoipCallFlow extends models.Model {
    _name = "voip.call.flow";

    graph_data = fields.Json();
    name = fields.Char();

    _records = [
        {
            id: 1,
            name: "Main flow",
            graph_data: {
                nodes: [
                    {
                        id: "start",
                        type: "start",
                        position: { x: 100, y: 100 },
                        size: { width: 200, height: 120 },
                        outputs: [
                            {
                                id: "next",
                                direction: "output",
                                provides: "flow",
                                maxConnections: 1,
                            },
                        ],
                        data: { label: "Start" },
                        deletable: false,
                    },
                    {
                        id: "hangup",
                        type: "hangup",
                        position: { x: 400, y: 100 },
                        size: { width: 180, height: 90 },
                        input: { id: "input", direction: "input", accepts: ["flow"] },
                        outputs: [],
                        data: { label: "Hang Up" },
                        deletable: true,
                    },
                ],
                connections: [
                    {
                        id: "connection",
                        sourceNodeId: "start",
                        sourcePortId: "next",
                        targetNodeId: "hangup",
                        targetPortId: "input",
                    },
                ],
            },
        },
        {
            id: 2,
            name: "Disconnected flow",
            graph_data: {
                nodes: [
                    {
                        id: "start",
                        type: "start",
                        position: { x: 50, y: 50 },
                        size: { width: 200, height: 120 },
                        outputs: [
                            {
                                id: "next",
                                direction: "output",
                                provides: "flow",
                                maxConnections: 1,
                            },
                        ],
                        data: { label: "Start" },
                        deletable: false,
                    },
                    {
                        id: "hangup2",
                        type: "hangup",
                        position: { x: 400, y: 50 },
                        size: { width: 180, height: 90 },
                        input: { id: "input", direction: "input", accepts: ["flow"] },
                        outputs: [],
                        data: { label: "Hang Up" },
                        deletable: true,
                    },
                ],
                connections: [],
            },
        },
    ];
}

class VoipDidNumber extends models.Model {
    _name = "voip.did.number";

    destination_ref = fields.Char();
    display_name = fields.Char();
}

defineModels({ ...mailModels, VoipCallFlow, VoipDidNumber });

test.tags("desktop");

test("loads, discards and saves a Call Flow through the form lifecycle", async () => {
    let savedGraph;
    onRpc("voip.call.flow", "web_save", ({ args }) => {
        savedGraph = args[1].graph_data;
    });
    await mountView({
        resModel: "voip.call.flow",
        resId: 1,
        type: "form",
        arch: `
            <form>
                <sheet>
                    <field name="graph_data" widget="voip_call_flow_editor"/>
                </sheet>
            </form>`,
    });

    await expect(".o_flow_editor_node").toHaveCount(2);
    await contains('article.o_flow_editor_node[aria-label="Hang Up"]').click();
    await contains('article.o_flow_editor_node[aria-label="Hang Up"]').press("Delete");
    await expect(".o_flow_editor_node").toHaveCount(1);
    expect(".o_form_status_indicator_buttons").not.toHaveClass("invisible");

    await clickCancel();
    await expect(".o_flow_editor_node").toHaveCount(2);
    expect(".o_form_status_indicator_buttons").toHaveClass("invisible");

    await contains('article.o_flow_editor_node[aria-label="Hang Up"]').click();
    await contains('article.o_flow_editor_node[aria-label="Hang Up"]').press("Delete");
    await clickSave();
    expect(savedGraph.nodes.map(({ id }) => id)).toEqual(["start"]);
    expect(savedGraph.connections).toEqual([]);
    expect(".o_form_status_indicator_buttons").toHaveClass("invisible");
});

test("zooming alone marks the form dirty and persists once the gesture settles", async () => {
    let savedGraph;
    onRpc("voip.call.flow", "web_save", ({ args }) => {
        savedGraph = args[1].graph_data;
    });
    await mountView({
        resModel: "voip.call.flow",
        resId: 1,
        type: "form",
        arch: `
            <form>
                <sheet>
                    <field name="graph_data" widget="voip_call_flow_editor"/>
                </sheet>
            </form>`,
    });

    await contains('[aria-label="Zoom in"]').click();
    // The debounced record update hasn't fired yet: still clean.
    expect(".o_form_status_indicator_buttons").toHaveClass("invisible");

    await advanceTime(300);
    expect(".o_form_status_indicator_buttons").not.toHaveClass("invisible");

    await clickSave();

    expect(savedGraph.viewport.scale).toBe(1.1);
});

test("dropping a Hang Up palette item creates a terminal node without opening a dialog", async () => {
    let savedGraph;
    onRpc("voip.call.flow", "web_save", ({ args }) => {
        savedGraph = args[1].graph_data;
    });
    await mountView({
        resModel: "voip.call.flow",
        resId: 1,
        type: "form",
        arch: `
            <form>
                <sheet>
                    <field name="graph_data" widget="voip_call_flow_editor"/>
                </sheet>
            </form>`,
    });
    await expect(".o_flow_editor_node").toHaveCount(2);

    await contains('.o_flow_node_palette_item[title="Hang Up"]').dragAndDrop(".o_flow_editor");

    await expect(".o_flow_editor_node").toHaveCount(3);
    expect(".o_dialog").toHaveCount(0);

    await clickSave();
    expect(savedGraph.nodes.filter((node) => node.type === "hangup").length).toBe(2);
});

test("dragging an existing node persists its new position", async () => {
    let savedGraph;
    onRpc("voip.call.flow", "web_save", ({ args }) => {
        savedGraph = args[1].graph_data;
    });
    await mountView({
        resModel: "voip.call.flow",
        resId: 1,
        type: "form",
        arch: `
            <form>
                <sheet>
                    <field name="graph_data" widget="voip_call_flow_editor"/>
                </sheet>
            </form>`,
    });

    await contains('article.o_flow_editor_node[aria-label="Hang Up"]').dragAndDrop(
        ".o_flow_editor",
        { position: "bottom-right" }
    );

    await clickSave();
    const hangupNode = savedGraph.nodes.find((node) => node.id === "hangup");
    expect(hangupNode.position).not.toEqual({ x: 400, y: 100 });
});

describe("CallFlowField: pure state updates", () => {
    function makeField({ nodes = [], connections = [], viewport = { x: 0, y: 0, scale: 1 } } = {}) {
        const updates = [];
        const editor = Object.assign(Object.create(CallFlowField.prototype), {
            state: proxy({ nodes, connections }),
            viewport,
            updates,
            props: {
                name: "graph_data",
                record: {
                    resId: 1,
                    update: (values) => {
                        updates.push(values.graph_data);
                        return Promise.resolve();
                    },
                },
            },
        });
        // Real components get this from useDebounced (setup() isn't run on
        // this bare prototype instance); call it straight through instead.
        editor.debouncedUpdateRecord = () => editor.updateRecord();
        return editor;
    }

    test("addNode keeps an unconfigured record node out of the graph", () => {
        const editor = makeField();
        editor.nextNodeId = 1;
        editor.registry = {
            create: (_type, values) => ({
                ...values,
                type: "audio_message",
                size: { width: 200, height: 120 },
                outputs: [],
                data: {},
            }),
            get: () => ({ size: { width: 200, height: 120 } }),
            getNodeConfiguration: () => ({}),
        };
        let configuration;
        editor.configureNode = (node, options) => {
            configuration = { node, options };
        };

        editor.addNode("audio_message", { x: 300, y: 200 });

        expect(configuration.node.type).toBe("audio_message");
        expect(configuration.options).toEqual({ removeOnCancel: true });
        expect(editor.state.nodes).toEqual([]);
        expect(editor.updates).toEqual([]);
    });

    test("clicking a Time Condition opens its form", () => {
        const node = {
            type: "time_condition",
            record: { resModel: "voip.time.condition", resId: 7 },
        };
        const editor = makeField({ nodes: [node] });
        editor.registry = { getNodeConfiguration: () => undefined };
        editor.openNodeRecord = (value) => expect.step(value === node ? "form opened" : "wrong");

        editor.onNodeClick({ node });

        expect.verifySteps(["form opened"]);
    });

    test("applying a new node adds it to the graph", async () => {
        const editor = makeField();
        editor.notification = { add() {} };
        editor.registry = { get: () => ({ validate: () => true }) };
        const node = {
            id: "audio_message-1",
            type: "audio_message",
            position: { x: 200, y: 140 },
            size: { width: 200, height: 120 },
            record: {
                resModel: "voip.sound",
                resId: 7,
                data: { display_name: "Welcome" },
            },
            outputs: [],
            data: {},
        };

        await editor.applyNodeConfiguration(node);

        expect(editor.state.nodes).toEqual([node]);
        expect(editor.updates.at(-1).nodes).toEqual([node]);
    });

    test("onConnect appends the connection and persists it", () => {
        const editor = makeField();
        const connection = {
            id: "c1",
            sourceNodeId: "start",
            sourcePortId: "next",
            targetNodeId: "hangup",
            targetPortId: "input",
        };

        const result = editor.onConnect(connection);

        expect(result).toBe(connection);
        expect(editor.state.connections).toEqual([connection]);
        expect(editor.updates.at(-1).connections).toEqual([connection]);
    });

    test("onDisconnect removes the connection and persists it", () => {
        const connection = { id: "c1", sourceNodeId: "start", targetNodeId: "hangup" };
        const editor = makeField({ connections: [connection] });

        const result = editor.onDisconnect({ connection });

        expect(result).toBe(true);
        expect(editor.state.connections).toEqual([]);
        expect(editor.updates.at(-1).connections).toEqual([]);
    });

    test("onNodeDrag persists the node position only once the drag ends", () => {
        const editor = makeField({
            nodes: [{ id: "a", position: { x: 0, y: 0 }, outputs: [], data: {} }],
        });

        editor.onNodeDrag({ node: { id: "a", position: { x: 5, y: 5 } }, phase: "move" });
        expect(editor.updates.length).toBe(0);

        editor.onNodeDrag({ node: { id: "a", position: { x: 50, y: 60 } }, phase: "end" });
        expect(editor.state.nodes[0].position).toEqual({ x: 50, y: 60 });
        expect(editor.updates.at(-1).nodes[0].position).toEqual({ x: 50, y: 60 });
    });

    test("onNodeResize marks the node as manually resized only once the resize ends", () => {
        const editor = makeField({
            nodes: [
                {
                    id: "a",
                    position: { x: 0, y: 0 },
                    size: { width: 220, height: 120 },
                    outputs: [],
                    data: {},
                },
            ],
        });

        const resizedNode = {
            id: "a",
            position: { x: 0, y: 0 },
            size: { width: 300, height: 120 },
        };
        editor.onNodeResize({ node: resizedNode, phase: "move" });
        expect(editor.updates.length).toBe(0);

        editor.onNodeResize({ node: resizedNode, phase: "end" });
        expect(editor.state.nodes[0].data.manuallyResized).toBe(true);
        expect(editor.updates.length).toBe(1);
    });

    test("onNodeDelete removes the node and persists it", () => {
        const editor = makeField({
            nodes: [{ id: "a", outputs: [], data: {} }],
        });

        const result = editor.onNodeDelete({ node: { id: "a" } });

        expect(result).toBe(true);
        expect(editor.state.nodes).toEqual([]);
        expect(editor.updates.at(-1).nodes).toEqual([]);
    });

    test("onViewportChange updates the local viewport and persists it", () => {
        const editor = makeField();

        editor.onViewportChange({ x: 10, y: 20, scale: 1.5 });

        expect(editor.viewport).toEqual({ x: 10, y: 20, scale: 1.5 });
        expect(editor.updates.at(-1).viewport).toEqual({ x: 10, y: 20, scale: 1.5 });
    });

    test("onConnectionRejected notifies with a message matching the rejection reason", () => {
        const notifications = [];
        const editor = makeField();
        editor.notification = {
            add: (message, options) => notifications.push({ message, options }),
        };

        editor.onConnectionRejected({ validation: { reason: "duplicate" } });

        expect(notifications).toEqual([
            { message: "This connection already exists.", options: { type: "warning" } },
        ]);
    });

    test("an unknown rejection reason falls back to a generic message", () => {
        const notifications = [];
        const editor = makeField();
        editor.notification = {
            add: (message, options) => notifications.push({ message, options }),
        };

        editor.onConnectionRejected({ validation: { reason: "something_new" } });

        expect(notifications).toEqual([
            { message: "This connection is not allowed.", options: { type: "warning" } },
        ]);
    });
});
