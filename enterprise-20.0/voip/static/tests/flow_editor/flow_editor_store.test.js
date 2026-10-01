/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import { FlowEditorStore } from "@voip/core/flow_editor/flow_editor_store";

test.tags("headless");

function node(id, position = { x: 0, y: 0 }) {
    return {
        id,
        type: "test",
        position,
        input: {
            id: "input",
            direction: "input",
            accepts: ["flow"],
        },
        outputs: [
            {
                id: "output",
                direction: "output",
                provides: "flow",
            },
        ],
    };
}

function connection(id, sourceNodeId, targetNodeId) {
    return {
        id,
        sourceNodeId,
        sourcePortId: "output",
        targetNodeId,
        targetPortId: "input",
    };
}

describe("FlowEditorStore", () => {
    test("adds and removes nodes together with their connections", () => {
        const store = new FlowEditorStore();
        expect(store.addNode(node("first"))).toBe(true);
        expect(store.addNode(node("second"))).toBe(true);
        expect(store.addNode(node("first"))).toBe(false);
        expect(store.addConnection(connection("connection", "first", "second"))).toBe(true);

        expect(store.removeNode("first")).toBe(true);
        expect(store.nodes.map(({ id }) => id)).toEqual(["second"]);
        expect(store.connections).toEqual([]);
    });

    test("adds and removes connections without accepting duplicate ids", () => {
        const graphConnection = connection("connection", "first", "second");
        const store = new FlowEditorStore({
            nodes: [node("first"), node("second")],
        });

        expect(store.addConnection(graphConnection)).toBe(true);
        expect(store.addConnection(graphConnection)).toBe(false);
        expect(store.removeConnection("connection")).toBe(true);
        expect(store.removeConnection("connection")).toBe(false);
    });

    test("keeps only existing unique items in a multiple selection", () => {
        const store = new FlowEditorStore({
            nodes: [node("first"), node("second")],
            connections: [connection("connection", "first", "second")],
        });

        store.setSelection({
            nodeIds: ["first", "missing", "first", "second"],
            connectionIds: ["missing", "connection", "connection"],
        });

        expect(store.selection).toEqual({
            nodeIds: ["first", "second"],
            connectionIds: ["connection"],
        });
    });

    test("cancels a node drag by restoring its original position", () => {
        const origin = { x: 10, y: 20 };
        const store = new FlowEditorStore({ nodes: [node("first", origin)] });
        expect(
            store.startInteraction({
                type: "node_drag",
                nodeId: "first",
                origin,
            })
        ).toBe(true);
        store.moveNode("first", { x: 100, y: 200 });

        store.cancelInteraction();

        expect(store.getNode("first").position).toEqual(origin);
        expect(store.interaction).toBe(null);
    });
});
