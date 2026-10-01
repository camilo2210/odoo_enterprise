/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import { patch } from "@web/core/utils/patch";
import { FlowNodePalette } from "@voip/flow_editor/flow_node_palette";

test.tags("headless");

function getGetter(name) {
    return Object.getOwnPropertyDescriptor(FlowNodePalette.prototype, name).get;
}

function makeRegistry(types) {
    return {
        getAll: () => types,
        getCategories: () => [{ id: "call_routing" }, { id: "flow_control" }],
        get: (type) => types.find((definition) => definition.type === type),
        canCreate: (type, nodes) => {
            const definition = types.find((definition) => definition.type === type);
            return !definition.unique || !nodes.some((node) => node.type === type);
        },
    };
}

function makePalette({ registry, nodes = [], onDrop = () => {}, onSelect = () => {} } = {}) {
    return {
        activePointerId: null,
        pointerDownPosition: null,
        state: {
            draggingType: null,
            isDragging: false,
            overCanvas: false,
            pointerX: 0,
            pointerY: 0,
        },
        props: { registry, nodes, onDrop, onSelect },
        cancelDrag: FlowNodePalette.prototype.cancelDrag,
    };
}

function pointerEvent({ pointerId = 1, button = 0, clientX = 0, clientY = 0 } = {}) {
    return { pointerId, button, clientX, clientY, preventDefault: () => {} };
}

function withElementFromPoint(element, callback) {
    const unpatch = patch(document, { elementFromPoint: () => element });
    try {
        return callback();
    } finally {
        unpatch();
    }
}

describe("FlowNodePalette", () => {
    test("items only include palette-flagged entries and are annotated with availability", () => {
        const registry = makeRegistry([
            { type: "start", category: "flow_control", palette: false, unique: true },
            { type: "hangup", category: "flow_control", palette: true, unique: false },
            { type: "queue", category: "call_routing", palette: true, unique: true },
        ]);
        const palette = makePalette({ registry, nodes: [{ type: "queue" }] });

        expect(getGetter("items").call(palette)).toEqual([
            {
                type: "queue",
                category: "call_routing",
                palette: true,
                unique: true,
                available: false,
            },
            {
                type: "hangup",
                category: "flow_control",
                palette: true,
                unique: false,
                available: true,
            },
        ]);
    });

    test("ghost is null while idle and centers on the pointer while dragging", () => {
        const registry = makeRegistry([
            { type: "queue", category: "call_routing", size: { width: 200, height: 140 } },
        ]);
        const palette = makePalette({ registry });

        expect(getGetter("ghost").call(palette)).toBe(null);

        Object.assign(palette.state, {
            draggingType: "queue",
            isDragging: true,
            pointerX: 150,
            pointerY: 100,
        });
        expect(getGetter("ghost").call(palette)).toEqual({
            type: "queue",
            category: "call_routing",
            size: { width: 200, height: 140 },
            style: "left: 50px; top: 30px; width: 200px; height: 140px;",
        });
    });

    test("a pointerdown starts a drag only on the primary button for an available type", () => {
        const registry = makeRegistry([{ type: "queue", unique: true }]);
        const palette = makePalette({ registry, nodes: [{ type: "queue" }] });

        FlowNodePalette.prototype.onPointerDown.call(palette, "queue", pointerEvent({ button: 1 }));
        expect(palette.state.draggingType).toBe(null);

        FlowNodePalette.prototype.onPointerDown.call(palette, "queue", pointerEvent());
        expect(palette.state.draggingType).toBe(null);

        palette.props.nodes = [];
        FlowNodePalette.prototype.onPointerDown.call(
            palette,
            "queue",
            pointerEvent({ pointerId: 7, clientX: 40, clientY: 60 })
        );
        expect(palette.activePointerId).toBe(7);
        expect(palette.state).toEqual({
            draggingType: "queue",
            isDragging: false,
            overCanvas: false,
            pointerX: 40,
            pointerY: 60,
        });
    });

    test("a pointermove is ignored outside the active drag and tracks canvas hover otherwise", () => {
        const palette = makePalette({ registry: makeRegistry([]) });
        palette.activePointerId = 1;
        palette.pointerDownPosition = { x: 0, y: 0 };
        Object.assign(palette.state, { draggingType: "queue" });

        FlowNodePalette.prototype.onPointerMove.call(palette, pointerEvent({ pointerId: 2 }));
        expect(palette.state.pointerX).toBe(0);

        const outside = document.createElement("div");
        withElementFromPoint(outside, () =>
            FlowNodePalette.prototype.onPointerMove.call(
                palette,
                pointerEvent({ clientX: 12, clientY: 34 })
            )
        );
        expect(palette.state).toEqual({
            draggingType: "queue",
            isDragging: true,
            overCanvas: false,
            pointerX: 12,
            pointerY: 34,
        });

        const canvas = document.createElement("div");
        canvas.className = "o_flow_editor";
        const overCanvasTarget = document.createElement("div");
        canvas.appendChild(overCanvasTarget);
        withElementFromPoint(overCanvasTarget, () =>
            FlowNodePalette.prototype.onPointerMove.call(palette, pointerEvent())
        );
        expect(palette.state.overCanvas).toBe(true);
    });

    test("dropping over the canvas reports the drop then always clears the drag", () => {
        const canvas = document.createElement("div");
        canvas.className = "o_flow_editor";
        canvas.getBoundingClientRect = () => ({ left: 10, top: 20, width: 300, height: 400 });

        const drops = [];
        const palette = makePalette({
            registry: makeRegistry([]),
            onDrop: (drop) => drops.push(drop),
        });
        palette.activePointerId = 1;
        Object.assign(palette.state, { draggingType: "queue", isDragging: true });

        withElementFromPoint(canvas, () =>
            FlowNodePalette.prototype.onPointerUp.call(
                palette,
                pointerEvent({ clientX: 55, clientY: 65 })
            )
        );

        expect(drops).toEqual([
            {
                type: "queue",
                clientX: 55,
                clientY: 65,
                canvasRect: { left: 10, top: 20, width: 300, height: 400 },
            },
        ]);
        expect(palette.activePointerId).toBe(null);
        expect(palette.state.draggingType).toBe(null);
    });

    test("dropping outside the canvas clears the drag without selecting or reporting a drop", () => {
        const drops = [];
        const selections = [];
        const palette = makePalette({
            registry: makeRegistry([]),
            onDrop: (drop) => drops.push(drop),
            onSelect: (type) => selections.push(type),
        });
        palette.activePointerId = 1;
        Object.assign(palette.state, { draggingType: "queue", isDragging: true });

        withElementFromPoint(document.createElement("div"), () =>
            FlowNodePalette.prototype.onPointerUp.call(palette, pointerEvent())
        );

        expect(drops).toEqual([]);
        expect(selections).toEqual([]);
        expect(palette.activePointerId).toBe(null);
        expect(palette.state.draggingType).toBe(null);
        expect(palette.state.isDragging).toBe(false);
    });

    test("releasing without dragging selects the palette item", () => {
        const drops = [];
        const selections = [];
        const palette = makePalette({
            registry: makeRegistry([]),
            onDrop: (drop) => drops.push(drop),
            onSelect: (type) => selections.push(type),
        });
        palette.activePointerId = 1;
        Object.assign(palette.state, { draggingType: "queue" });

        withElementFromPoint(document.createElement("div"), () =>
            FlowNodePalette.prototype.onPointerUp.call(palette, pointerEvent())
        );

        expect(drops).toEqual([]);
        expect(selections).toEqual(["queue"]);
        expect(palette.state.draggingType).toBe(null);
    });

    test("the drag is cleared even when the drop handler throws", () => {
        const canvas = document.createElement("div");
        canvas.className = "o_flow_editor";
        canvas.getBoundingClientRect = () => ({});
        const palette = makePalette({
            registry: makeRegistry([]),
            onDrop: () => {
                throw new Error("boom");
            },
        });
        palette.activePointerId = 1;
        Object.assign(palette.state, { draggingType: "queue", isDragging: true });

        expect(() =>
            withElementFromPoint(canvas, () =>
                FlowNodePalette.prototype.onPointerUp.call(palette, pointerEvent())
            )
        ).toThrow("boom");
        expect(palette.state.draggingType).toBe(null);
        expect(palette.activePointerId).toBe(null);
    });
});
