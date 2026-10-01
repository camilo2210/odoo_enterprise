/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import { patch } from "@web/core/utils/patch";
import { FlowEditor } from "@voip/core/flow_editor/flow_editor";
import { FlowEditorStore } from "@voip/core/flow_editor/flow_editor_store";

test.tags("headless");

const DEFAULT_NODE_SIZE = { width: 220, height: 120 };
const MIN_NODE_SIZE = { width: 120, height: 80 };

function node(id, overrides = {}) {
    return {
        id,
        type: "test",
        position: { x: 0, y: 0 },
        outputs: [],
        ...overrides,
    };
}

function connection(id, sourceNodeId, targetNodeId, overrides = {}) {
    return {
        id,
        sourceNodeId,
        sourcePortId: "output",
        targetNodeId,
        targetPortId: "input",
        ...overrides,
    };
}

function pointerEvent(overrides = {}) {
    return {
        pointerId: 1,
        button: 0,
        clientX: 0,
        clientY: 0,
        altKey: false,
        target: { closest: () => null },
        preventDefault: () => {},
        stopPropagation: () => {},
        ...overrides,
    };
}

function wheelEvent(overrides = {}) {
    return {
        ctrlKey: true,
        metaKey: false,
        deltaY: -1,
        clientX: 0,
        clientY: 0,
        preventDefault: () => {},
        ...overrides,
    };
}

function withElementFromPoint(element, callback) {
    const unpatch = patch(document, { elementFromPoint: () => element });
    try {
        return callback();
    } finally {
        unpatch();
    }
}

function portElement({ nodeId, portId, direction }) {
    const el = {
        dataset: { nodeId, portId, portDirection: direction },
    };
    el.closest = (selector) => (selector === `.o_flow_editor_port_${direction}` ? el : null);
    return el;
}

function makeEditor({
    nodes = [],
    connections = [],
    readonly = false,
    props = {},
    canvasRect = { left: 0, top: 0, width: 800, height: 600 },
} = {}) {
    const store = new FlowEditorStore({ nodes, connections, readonly });
    const canvasEl = {
        getBoundingClientRect: () => canvasRect,
        focus: () => {},
        contains: () => true,
    };
    return Object.assign(Object.create(FlowEditor.prototype), {
        canvasRef: () => canvasEl,
        props: {
            allowSelfConnections: false,
            canConnect: () => true,
            defaultNodeHeaderHeight: 32,
            defaultNodeSize: DEFAULT_NODE_SIZE,
            gridSize: 20,
            minNodeSize: MIN_NODE_SIZE,
            onConnect: (candidate) => candidate,
            onConnectionRejected: () => {},
            onDisconnect: () => true,
            onDrag: () => {},
            onNodeClick: () => {},
            onNodeDelete: () => true,
            onPan: () => {},
            onResize: () => {},
            onSelectionChange: () => {},
            onViewportChange: () => {},
            ...props,
        },
        store,
    });
}

test("deletion vetoes do not prevent deleting other selected nodes", async () => {
    const protectedByDisconnect = node("protected-by-disconnect");
    const protectedByNodeDelete = node("protected-by-node-delete");
    const deletable = node("deletable");
    const target = node("target");
    const protectedConnection = {
        id: "protected-connection",
        sourceNodeId: protectedByDisconnect.id,
        sourcePortId: "output",
        targetNodeId: target.id,
        targetPortId: "input",
    };
    const store = new FlowEditorStore({
        nodes: [protectedByDisconnect, protectedByNodeDelete, deletable, target],
        connections: [protectedConnection],
    });
    store.setSelection({
        nodeIds: [protectedByDisconnect.id, protectedByNodeDelete.id, deletable.id],
        connectionIds: [protectedConnection.id],
    });
    let selectionChangeCount = 0;
    let prevented = false;
    const editor = {
        canvasRef: () => ({ contains: () => true }),
        deleteNode: FlowEditor.prototype.deleteNode,
        notifySelectionChange: () => selectionChangeCount++,
        props: {
            onDisconnect: ({ connection }) => connection.id !== protectedConnection.id,
            onNodeDelete: ({ node: graphNode }) => graphNode.id !== protectedByNodeDelete.id,
        },
        store,
    };

    await FlowEditor.prototype.onKeyDown.call(editor, {
        key: "Delete",
        preventDefault: () => {
            prevented = true;
        },
    });

    expect(prevented).toBe(true);
    expect(store.nodes.map(({ id }) => id)).toEqual([
        protectedByDisconnect.id,
        protectedByNodeDelete.id,
        target.id,
    ]);
    expect(store.connections.map(({ id }) => id)).toEqual([protectedConnection.id]);
    expect(store.selection).toEqual({
        nodeIds: [protectedByDisconnect.id, protectedByNodeDelete.id],
        connectionIds: [protectedConnection.id],
    });
    expect(selectionChangeCount).toBe(1);
});

describe("FlowEditor: canvas panning", () => {
    test("a pointerdown on empty canvas starts a pan that translates the viewport", () => {
        const editor = makeEditor();

        editor.onCanvasPointerDown(pointerEvent({ clientX: 100, clientY: 100 }));
        expect(editor.store.interaction).toEqual({ type: "pan" });

        editor.onPointerMove(pointerEvent({ clientX: 130, clientY: 150 }));
        expect(editor.store.viewport).toEqual({ x: 30, y: 50, scale: 1 });

        editor.onPointerUp(pointerEvent({ clientX: 130, clientY: 150 }));
        expect(editor.store.interaction).toBe(null);
    });

    test("a pointerdown on a node, connection or control does not start a pan", () => {
        const editor = makeEditor();

        editor.onCanvasPointerDown(pointerEvent({ target: { closest: () => ({}) } }));

        expect(editor.store.interaction).toBe(null);
    });

    test("a middle-button pointerdown also starts a pan, a right-button one does not", () => {
        const middleButton = makeEditor();
        middleButton.onCanvasPointerDown(pointerEvent({ button: 1 }));
        expect(middleButton.store.interaction).toEqual({ type: "pan" });

        const rightButton = makeEditor();
        rightButton.onCanvasPointerDown(pointerEvent({ button: 2 }));
        expect(rightButton.store.interaction).toBe(null);
    });

    test("readonly still allows panning", () => {
        const editor = makeEditor({ readonly: true });

        editor.onCanvasPointerDown(pointerEvent());

        expect(editor.store.interaction).toEqual({ type: "pan" });
    });
});

describe("FlowEditor: node dragging", () => {
    test("dragging a node moves it and reports every phase", () => {
        const draggedNode = node("a", { position: { x: 50, y: 60 } });
        const editor = makeEditor({ nodes: [draggedNode] });
        const phases = [];
        editor.props.onDrag = (payload) => phases.push(payload.phase);

        editor.onNodePointerDown({
            node: draggedNode,
            originalEvent: pointerEvent({ clientX: 100, clientY: 100 }),
        });
        expect(editor.store.interaction.type).toBe("node_drag");
        expect(editor.store.selection.nodeIds).toEqual(["a"]);

        editor.onPointerMove(pointerEvent({ clientX: 140, clientY: 150 }));
        expect(editor.store.getNode("a").position).toEqual({ x: 90, y: 110 });

        editor.onPointerUp(pointerEvent({ clientX: 140, clientY: 150 }));

        expect(phases).toEqual(["start", "move", "end"]);
        expect(editor.store.interaction).toBe(null);
        expect(editor.suppressNodeClick).toBe(true);
    });

    test("holding alt snaps the dragged position to the grid", () => {
        const draggedNode = node("a", { position: { x: 0, y: 0 } });
        const editor = makeEditor({ nodes: [draggedNode] });

        editor.onNodePointerDown({
            node: draggedNode,
            originalEvent: pointerEvent({ clientX: 0, clientY: 0, altKey: true }),
        });
        editor.onPointerMove(pointerEvent({ clientX: 34, clientY: 6 }));

        // gridSize is 20: (34, 6) snaps to the nearest multiple of 20.
        expect(editor.store.getNode("a").position).toEqual({ x: 40, y: 0 });
    });

    test("a click without prior movement does not suppress the next node click", () => {
        const draggedNode = node("a");
        const editor = makeEditor({ nodes: [draggedNode] });

        editor.onNodePointerDown({ node: draggedNode, originalEvent: pointerEvent() });
        editor.onPointerUp(pointerEvent());

        expect(editor.suppressNodeClick).toBe(false);
    });

    test("dragging a readonly node is not allowed to start", () => {
        const readonlyNode = node("a", { readonly: true });
        const editor = makeEditor({ nodes: [readonlyNode] });

        editor.onNodePointerDown({ node: readonlyNode, originalEvent: pointerEvent() });

        expect(editor.store.interaction).toBe(null);
    });
});

describe("FlowEditor: node resizing", () => {
    test("resizing a node reports every phase and respects the minimum size", () => {
        const resizedNode = node("a");
        const editor = makeEditor({ nodes: [resizedNode] });
        const phases = [];
        editor.props.onResize = (payload) =>
            phases.push({ phase: payload.phase, size: payload.size });

        editor.onResizePointerDown({
            node: resizedNode,
            originalEvent: pointerEvent({ clientX: 200, clientY: 200 }),
        });
        expect(editor.store.interaction.origin).toEqual(DEFAULT_NODE_SIZE);

        editor.onPointerMove(pointerEvent({ clientX: 260, clientY: 170 }));
        // width grows by 60, height would shrink by 30 but is clamped to minNodeSize.height.
        expect(editor.store.getNode("a").size).toEqual({ width: 280, height: 90 });

        editor.onPointerUp(pointerEvent({ clientX: 260, clientY: 170 }));

        expect(phases.map((entry) => entry.phase)).toEqual(["start", "move", "end"]);
        expect(phases.at(-1).size).toEqual({ width: 280, height: 90 });
    });

    test("a circle-shaped node cannot be resized", () => {
        const circleNode = node("a", { shape: "circle" });
        const editor = makeEditor({ nodes: [circleNode] });

        editor.onResizePointerDown({ node: circleNode, originalEvent: pointerEvent() });

        expect(editor.store.interaction).toBe(null);
    });
});

describe("FlowEditor: zoom controls", () => {
    test("zoomIn increases the scale around the canvas center", () => {
        const editor = makeEditor();
        const scale = 1 * 1.1;

        editor.zoomIn();

        // Computed rather than hardcoded: 400 * 1.1 is not bit-exact in IEEE 754.
        expect(editor.store.viewport).toEqual({
            x: 400 - 400 * scale,
            y: 300 - 300 * scale,
            scale,
        });
    });

    test("zoomOut decreases the scale around the canvas center", () => {
        const editor = makeEditor();
        const scale = 1 * 0.9;

        editor.zoomOut();

        expect(editor.store.viewport).toEqual({
            x: 400 - 400 * scale,
            y: 300 - 300 * scale,
            scale,
        });
    });

    test("ctrl+wheel zooms around the pointer position", () => {
        const editor = makeEditor();
        const scale = 1 * 1.1;

        editor.onWheel(wheelEvent({ clientX: 200, clientY: 100, deltaY: -1 }));

        expect(editor.store.viewport).toEqual({
            x: 200 - 200 * scale,
            y: 100 - 100 * scale,
            scale,
        });
    });

    test("wheel without a modifier key is ignored", () => {
        const editor = makeEditor();

        editor.onWheel(wheelEvent({ ctrlKey: false, metaKey: false }));

        expect(editor.store.viewport).toEqual({ x: 0, y: 0, scale: 1 });
    });
});

describe("FlowEditor: fit to content", () => {
    test("resets the viewport when there are no nodes", () => {
        const editor = makeEditor();
        editor.store.setViewport({ x: 500, y: 500, scale: 2 });

        editor.fitToContent();

        expect(editor.store.viewport).toEqual({ x: 0, y: 0, scale: 1 });
    });

    test("centers and scales the viewport to fit every node", () => {
        const editor = makeEditor({
            nodes: [
                node("a", { position: { x: 0, y: 0 }, size: { width: 200, height: 100 } }),
                node("b", { position: { x: 300, y: 400 }, size: { width: 100, height: 50 } }),
            ],
        });

        editor.fitToContent();

        expect(editor.store.viewport).toEqual({ x: 200, y: 75, scale: 1 });
    });
});

describe("FlowEditor: connecting ports", () => {
    function makeConnectableEditor(overrides = {}) {
        return makeEditor({
            nodes: [
                node("a", {
                    position: { x: 0, y: 0 },
                    outputs: [
                        { id: "out", direction: "output", provides: "flow", maxConnections: 1 },
                    ],
                }),
                node("b", {
                    position: { x: 300, y: 0 },
                    input: { id: "in", direction: "input", accepts: ["flow"] },
                }),
                node("c", {
                    position: { x: 150, y: 300 },
                    input: { id: "in", direction: "input", accepts: ["flow"] },
                }),
            ],
            ...overrides,
        });
    }

    test("dragging from an output port to an input port creates a connection", async () => {
        const editor = makeConnectableEditor();
        const connects = [];
        editor.props.onConnect = (candidate) => {
            connects.push(candidate);
            return candidate;
        };

        editor.onPortPointerDown({
            nodeId: "a",
            port: { id: "out", direction: "output" },
            originalEvent: pointerEvent(),
        });
        expect(editor.store.interaction.type).toBe("connection_drag");

        const targetPort = portElement({ nodeId: "b", portId: "in", direction: "input" });
        await withElementFromPoint(targetPort, () => {
            editor.onPointerMove(pointerEvent({ clientX: 310, clientY: 5 }));
            return editor.onPointerUp(pointerEvent({ clientX: 310, clientY: 5 }));
        });

        expect(editor.store.connections).toEqual([
            {
                id: "flow-connection-1",
                sourceNodeId: "a",
                sourcePortId: "out",
                targetNodeId: "b",
                targetPortId: "in",
            },
        ]);
        expect(connects.length).toBe(1);
        expect(editor.store.interaction).toBe(null);
    });

    test("does not report a rejection when onConnect already synced the connection via props", async () => {
        const editor = makeConnectableEditor();
        const rejections = [];
        editor.props.onConnectionRejected = (payload) => rejections.push(payload.validation.reason);
        editor.props.onConnect = (candidate) => {
            // Simulates a consumer whose onConnect feeds the connection back
            // through reactive props before this async call resumes, so
            // onWillUpdateProps syncs it into the store via store.setGraph
            // ahead of connectPorts's own persisted-connection validation.
            editor.store.addConnection(candidate);
            return candidate;
        };

        editor.onPortPointerDown({
            nodeId: "a",
            port: { id: "out", direction: "output" },
            originalEvent: pointerEvent(),
        });
        const targetPort = portElement({ nodeId: "b", portId: "in", direction: "input" });
        await withElementFromPoint(targetPort, () => {
            editor.onPointerMove(pointerEvent({ clientX: 310, clientY: 5 }));
            return editor.onPointerUp(pointerEvent({ clientX: 310, clientY: 5 }));
        });

        expect(rejections).toEqual([]);
        expect(editor.store.connections.map(({ id }) => id)).toEqual(["flow-connection-1"]);
    });

    test("a connection rejected by the consumer is not created", async () => {
        const editor = makeConnectableEditor({ props: { canConnect: () => false } });
        const rejections = [];
        editor.props.onConnectionRejected = (payload) => rejections.push(payload.validation.reason);
        const connects = [];
        editor.props.onConnect = (candidate) => {
            connects.push(candidate);
            return candidate;
        };

        editor.onPortPointerDown({
            nodeId: "a",
            port: { id: "out", direction: "output" },
            originalEvent: pointerEvent(),
        });
        const targetPort = portElement({ nodeId: "b", portId: "in", direction: "input" });
        await withElementFromPoint(targetPort, () => {
            editor.onPointerMove(pointerEvent({ clientX: 310, clientY: 5 }));
            return editor.onPointerUp(pointerEvent({ clientX: 310, clientY: 5 }));
        });

        expect(editor.store.connections).toEqual([]);
        expect(connects).toEqual([]);
        expect(rejections).toEqual(["consumer_rejected"]);
    });

    test("connecting to a saturated output port replaces its existing connection", async () => {
        const editor = makeConnectableEditor({
            connections: [connection("c1", "a", "b", { sourcePortId: "out", targetPortId: "in" })],
        });
        const disconnected = [];
        editor.props.onDisconnect = ({ connection: removed }) => {
            disconnected.push(removed.id);
            return true;
        };

        editor.onPortPointerDown({
            nodeId: "c",
            port: { id: "in", direction: "input" },
            originalEvent: pointerEvent(),
        });
        expect(editor.store.connections.map(({ id }) => id)).toEqual(["c1"]);

        const sourcePort = portElement({ nodeId: "a", portId: "out", direction: "output" });
        await withElementFromPoint(sourcePort, () => {
            editor.onPointerMove(pointerEvent({ clientX: 5, clientY: 5 }));
            return editor.onPointerUp(pointerEvent({ clientX: 5, clientY: 5 }));
        });

        expect(disconnected).toEqual(["c1"]);
        expect(editor.store.connections).toEqual([
            {
                id: "flow-connection-1",
                sourceNodeId: "a",
                sourcePortId: "out",
                targetNodeId: "c",
                targetPortId: "in",
            },
        ]);
    });

    test("a saturated output port is not shown as invalid while hovering it", () => {
        const editor = makeConnectableEditor({
            connections: [connection("c1", "a", "b", { sourcePortId: "out", targetPortId: "in" })],
        });

        editor.onPortPointerDown({
            nodeId: "c",
            port: { id: "in", direction: "input" },
            originalEvent: pointerEvent(),
        });
        editor.store.updateConnectionDraft({ x: 0, y: 0 }, { nodeId: "a", portId: "out" });

        expect(editor.getPortValidation("a", "out")).toBe("valid");
    });

    test("a veto on the displaced connection keeps a saturated output port rejected", async () => {
        const editor = makeConnectableEditor({
            connections: [connection("c1", "a", "b", { sourcePortId: "out", targetPortId: "in" })],
        });
        editor.props.onDisconnect = () => false;
        const rejections = [];
        editor.props.onConnectionRejected = (payload) => rejections.push(payload.validation.reason);

        editor.onPortPointerDown({
            nodeId: "c",
            port: { id: "in", direction: "input" },
            originalEvent: pointerEvent(),
        });

        const sourcePort = portElement({ nodeId: "a", portId: "out", direction: "output" });
        await withElementFromPoint(sourcePort, () => {
            editor.onPointerMove(pointerEvent({ clientX: 5, clientY: 5 }));
            return editor.onPointerUp(pointerEvent({ clientX: 5, clientY: 5 }));
        });

        expect(editor.store.connections.map(({ id }) => id)).toEqual(["c1"]);
        expect(rejections).toEqual([]);
    });

    test("grabbing a connected input port reconnects it to a different node", async () => {
        const editor = makeConnectableEditor({
            connections: [connection("c1", "a", "b", { sourcePortId: "out", targetPortId: "in" })],
        });
        const disconnected = [];
        editor.props.onDisconnect = ({ connection: removed }) => {
            disconnected.push(removed.id);
            return true;
        };

        editor.onPortPointerDown({
            nodeId: "b",
            port: { id: "in", direction: "input" },
            originalEvent: pointerEvent(),
        });
        expect(disconnected).toEqual(["c1"]);
        expect(editor.store.connections).toEqual([]);

        const targetPort = portElement({ nodeId: "c", portId: "in", direction: "input" });
        await withElementFromPoint(targetPort, () => {
            editor.onPointerMove(pointerEvent({ clientX: 155, clientY: 305 }));
            return editor.onPointerUp(pointerEvent({ clientX: 155, clientY: 305 }));
        });

        expect(editor.store.connections).toEqual([
            {
                id: "flow-connection-1",
                sourceNodeId: "a",
                sourcePortId: "out",
                targetNodeId: "c",
                targetPortId: "in",
            },
        ]);
    });

    test("grabbing a connected output port reconnects it to a different node", async () => {
        const editor = makeConnectableEditor({
            connections: [connection("c1", "a", "b", { sourcePortId: "out", targetPortId: "in" })],
        });
        const disconnected = [];
        editor.props.onDisconnect = ({ connection: removed }) => {
            disconnected.push(removed.id);
            return true;
        };

        editor.onPortPointerDown({
            nodeId: "a",
            port: { id: "out", direction: "output" },
            originalEvent: pointerEvent(),
        });
        expect(disconnected).toEqual(["c1"]);
        expect(editor.store.connections).toEqual([]);

        const targetPort = portElement({ nodeId: "c", portId: "in", direction: "input" });
        await withElementFromPoint(targetPort, () => {
            editor.onPointerMove(pointerEvent({ clientX: 155, clientY: 305 }));
            return editor.onPointerUp(pointerEvent({ clientX: 155, clientY: 305 }));
        });

        expect(editor.store.connections).toEqual([
            {
                id: "flow-connection-1",
                sourceNodeId: "a",
                sourcePortId: "out",
                targetNodeId: "c",
                targetPortId: "in",
            },
        ]);
    });

    test("vetoing the disconnection keeps the original connection", () => {
        const editor = makeConnectableEditor({
            connections: [connection("c1", "a", "b", { sourcePortId: "out", targetPortId: "in" })],
            props: { onDisconnect: () => false },
        });

        editor.onPortPointerDown({
            nodeId: "b",
            port: { id: "in", direction: "input" },
            originalEvent: pointerEvent(),
        });

        expect(editor.store.connections.map(({ id }) => id)).toEqual(["c1"]);
        expect(editor.store.interaction).toBe(null);
    });

    test("connecting an output to its own node's input does not open the node afterward", async () => {
        const selfNode = node("a", {
            outputs: [{ id: "out", direction: "output", provides: "flow" }],
            input: { id: "in", direction: "input", accepts: ["flow"] },
        });
        const editor = makeEditor({
            nodes: [selfNode],
            props: { allowSelfConnections: true },
        });
        const clicks = [];
        editor.props.onNodeClick = (payload) => clicks.push(payload.node.id);

        editor.onPortPointerDown({
            nodeId: "a",
            port: { id: "out", direction: "output" },
            originalEvent: pointerEvent(),
        });
        const targetPort = portElement({ nodeId: "a", portId: "in", direction: "input" });
        await withElementFromPoint(targetPort, () => {
            editor.onPointerMove(pointerEvent({ clientX: 10, clientY: 10 }));
            return editor.onPointerUp(pointerEvent({ clientX: 10, clientY: 10 }));
        });

        expect(editor.store.connections).toEqual([
            {
                id: "flow-connection-1",
                sourceNodeId: "a",
                sourcePortId: "out",
                targetNodeId: "a",
                targetPortId: "in",
            },
        ]);
        expect(editor.suppressNodeClick).toBe(true);

        // Source and target ports share the same node <article>, so the
        // browser's own click-target resolution would otherwise synthesize
        // a click on that node right after the drag ends (see onPointerUp)
        // - it must be swallowed instead of opening the node's configuration.
        editor.onNodeClick({ node: editor.store.getNode("a"), originalEvent: {} });
        expect(clicks).toEqual([]);
    });
});

describe("FlowEditor: selection", () => {
    test("clicking a node selects it and notifies once", () => {
        const editor = makeEditor({ nodes: [node("a"), node("b")] });
        const clicks = [];
        editor.props.onNodeClick = (payload) => clicks.push(payload.node.id);
        let selectionChanges = 0;
        editor.props.onSelectionChange = () => selectionChanges++;

        editor.onNodeClick({ node: editor.store.getNode("a"), originalEvent: {} });

        expect(editor.store.selection.nodeIds).toEqual(["a"]);
        expect(editor.isNodeSelected("a")).toBe(true);
        expect(clicks).toEqual(["a"]);
        expect(selectionChanges).toBe(1);
    });

    test("a click right after a drag is suppressed exactly once", () => {
        const editor = makeEditor({ nodes: [node("a")] });
        editor.suppressNodeClick = true;
        const clicks = [];
        editor.props.onNodeClick = (payload) => clicks.push(payload.node.id);

        editor.onNodeClick({ node: editor.store.getNode("a"), originalEvent: {} });
        expect(clicks).toEqual([]);
        expect(editor.suppressNodeClick).toBe(false);

        editor.onNodeClick({ node: editor.store.getNode("a"), originalEvent: {} });
        expect(clicks).toEqual(["a"]);
    });

    test("clicking a connection selects it", () => {
        const editor = makeEditor({
            nodes: [
                node("a"),
                node("b", { input: { id: "input", direction: "input", accepts: ["flow"] } }),
            ],
            connections: [connection("c1", "a", "b")],
        });

        editor.onConnectionClick({ connectionId: "c1" });

        expect(editor.store.selection.connectionIds).toEqual(["c1"]);
        expect(editor.isConnectionSelected("c1")).toBe(true);
    });
});

describe("FlowEditor: keyboard", () => {
    test("Escape cancels an ongoing node drag and reverts its position", () => {
        const draggedNode = node("a", { position: { x: 10, y: 20 } });
        const editor = makeEditor({ nodes: [draggedNode] });
        const phases = [];
        editor.props.onDrag = (payload) => phases.push(payload.phase);

        editor.onNodePointerDown({
            node: draggedNode,
            originalEvent: pointerEvent({ clientX: 0, clientY: 0 }),
        });
        editor.onPointerMove(pointerEvent({ clientX: 90, clientY: 90 }));
        expect(editor.store.getNode("a").position).not.toEqual({ x: 10, y: 20 });

        editor.onKeyDown({ key: "Escape", preventDefault: () => {} });

        expect(editor.store.getNode("a").position).toEqual({ x: 10, y: 20 });
        expect(editor.store.interaction).toBe(null);
        expect(phases.at(-1)).toBe("cancel");
    });
});
