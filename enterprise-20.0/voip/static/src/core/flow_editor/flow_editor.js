import {
    Component,
    onWillDestroy,
    onWillUpdateProps,
    signal,
    t,
    useListener,
    useProps,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

import { normalizeConnectionValidation, validateConnection } from "./connection_validator";
import { FlowConnection } from "./flow_connection";
import { createFlowEditorStore } from "./flow_editor_store";
import { FlowNode } from "./flow_node";
import { buildConnectionGeometry } from "./geometry/connections";
import { clampScale, screenToWorld } from "./geometry/coordinates";
import { getNodeRect, getNodeSize, getObstacleRects } from "./geometry/nodes";
import { DEFAULT_NODE_HEADER_HEIGHT, getPortAnchor } from "./geometry/ports";
import { buildOrthogonalPath } from "./geometry/router";

const DEFAULT_NODE_SIZE = { width: 220, height: 120 };
const DEFAULT_MIN_NODE_SIZE = { width: 120, height: 80 };
const DEFAULT_GRID_SIZE = 20;

export class FlowEditor extends Component {
    static template = "voip.FlowEditor";
    static components = { FlowConnection, FlowNode };

    props = useProps({
        allowSelfConnections: t.boolean().optional(false),
        ariaLabel: t.string().optional(() => _t("Flow editor")),
        canConnect: t.function().optional(() => () => true),
        connections: t.array(),
        defaultNodeHeaderHeight: t.number().optional(DEFAULT_NODE_HEADER_HEIGHT),
        defaultNodeSize: t.object().optional(DEFAULT_NODE_SIZE),
        getNodeComponent: t.function().optional(() => () => undefined),
        gridSize: t.number().optional(DEFAULT_GRID_SIZE),
        minNodeSize: t.object().optional(DEFAULT_MIN_NODE_SIZE),
        NodeComponent: t.any().optional(),
        nodes: t.array(),
        onConnect: t.function().optional(() => (connection) => connection),
        onConnectionRejected: t.function().optional(() => () => {}),
        onDisconnect: t.function().optional(() => () => true),
        onDrag: t.function().optional(() => () => {}),
        onNodeDelete: t.function().optional(() => () => true),
        onNodeClick: t.function().optional(() => () => {}),
        onPan: t.function().optional(() => () => {}),
        onResize: t.function().optional(() => () => {}),
        onSelectionChange: t.function().optional(() => () => {}),
        onViewportChange: t.function().optional(() => () => {}),
        readonly: t.boolean().optional(false),
        showControls: t.boolean().optional(true),
        viewport: t.object().optional(() => ({ x: 0, y: 0, scale: 1 })),
    });

    canvasRef = signal(null);

    setup() {
        this.store = createFlowEditorStore({
            nodes: this.props.nodes,
            connections: this.props.connections,
            viewport: this.props.viewport,
            readonly: this.props.readonly,
        });
        onWillUpdateProps((nextProps) => {
            if (
                nextProps.nodes !== this.props.nodes ||
                nextProps.connections !== this.props.connections
            ) {
                this.store.setGraph({
                    nodes: nextProps.nodes,
                    connections: nextProps.connections,
                });
            }
            if (nextProps.viewport !== this.props.viewport) {
                this.store.setViewport(nextProps.viewport);
            }
            this.store.setReadonly(nextProps.readonly);
        });
        useListener(window, "pointermove", this.onPointerMove.bind(this));
        useListener(window, "pointerup", this.onPointerUp.bind(this));
        useListener(window, "pointercancel", this.onPointerCancel.bind(this));
        useListener(window, "keydown", this.onKeyDown.bind(this));
        onWillDestroy(() => this.cancelViewportAnimation());
    }

    get canvasStyle() {
        const { x, y, scale } = this.store.viewport;
        const gridSize = Math.max(this.props.gridSize, 1) * scale;
        return `background-size: ${gridSize}px ${gridSize}px; background-position: ${x}px ${y}px;`;
    }

    get contentStyle() {
        const { x, y, scale } = this.store.viewport;
        return `transform: translate(${x}px, ${y}px) scale(${scale});`;
    }

    get connectionGeometries() {
        return this.store.connections
            .map((connection) => {
                const sourceNode = this.store.getNode(connection.sourceNodeId);
                const targetNode = this.store.getNode(connection.targetNodeId);
                if (!sourceNode || !targetNode) {
                    return null;
                }
                return buildConnectionGeometry({
                    connection,
                    sourceNode,
                    targetNode,
                    nodes: this.store.nodes,
                    defaultNodeSize: this.props.defaultNodeSize,
                    defaultNodeHeaderHeight: this.props.defaultNodeHeaderHeight,
                });
            })
            .filter(Boolean);
    }

    /**
     * Geometry for a candidate end already hovering a valid port: delegates
     * to `buildConnectionGeometry`, the exact function a confirmed
     * connection renders with (self-loop shape included), so the preview
     * never has to jump to a different route once the drag is confirmed.
     *
     * @returns {ReturnType<typeof buildConnectionGeometry> | null}
     */
    _draftSnappedGeometry({ sourceNodeId, sourcePortId, targetNodeId, targetPortId }) {
        const sourceNode = this.store.getNode(sourceNodeId);
        const targetNode = this.store.getNode(targetNodeId);
        if (!sourceNode || !targetNode) {
            return null;
        }
        return buildConnectionGeometry({
            connection: {
                id: "flow-connection-draft",
                sourceNodeId,
                sourcePortId,
                targetNodeId,
                targetPortId,
            },
            sourceNode,
            targetNode,
            nodes: this.store.nodes,
            defaultNodeSize: this.props.defaultNodeSize,
            defaultNodeHeaderHeight: this.props.defaultNodeHeaderHeight,
        });
    }

    get draftConnectionGeometry() {
        if (this.store.interaction?.type !== "connection_drag") {
            return null;
        }
        const draft = this.store.interaction.connectionDraft;
        const { sourceNodeId, sourcePortId, pointer } = draft;
        if (draft.reconnectSource) {
            const snapped =
                draft.sourceCandidateNodeId &&
                this._draftSnappedGeometry({
                    sourceNodeId: draft.sourceCandidateNodeId,
                    sourcePortId: draft.sourceCandidatePortId,
                    targetNodeId: draft.targetNodeId,
                    targetPortId: draft.targetPortId,
                });
            if (snapped) {
                return snapped;
            }
            const targetNode = this.store.getNode(draft.targetNodeId);
            const end = targetNode
                ? getPortAnchor(
                      targetNode,
                      draft.targetPortId,
                      this.props.defaultNodeSize,
                      this.props.defaultNodeHeaderHeight
                  )
                : null;
            if (!end) {
                return null;
            }
            return {
                id: "flow-connection-draft",
                ...buildOrthogonalPath({
                    start: pointer,
                    end,
                    obstacles: getObstacleRects(this.store.nodes, {
                        defaultSize: this.props.defaultNodeSize,
                        padding: 20,
                        excludedNodeIds: new Set([draft.targetNodeId]),
                    }),
                }),
            };
        }
        const snapped =
            draft.targetNodeId &&
            this._draftSnappedGeometry({
                sourceNodeId,
                sourcePortId,
                targetNodeId: draft.targetNodeId,
                targetPortId: draft.targetPortId,
            });
        if (snapped) {
            return snapped;
        }
        const sourceNode = this.store.getNode(sourceNodeId);
        if (!sourceNode) {
            return null;
        }
        const start = getPortAnchor(
            sourceNode,
            sourcePortId,
            this.props.defaultNodeSize,
            this.props.defaultNodeHeaderHeight
        );
        if (!start) {
            return null;
        }
        const obstacles = getObstacleRects(this.store.nodes, {
            defaultSize: this.props.defaultNodeSize,
            padding: 20,
            excludedNodeIds: new Set([sourceNodeId]),
        });
        return {
            id: "flow-connection-draft",
            ...buildOrthogonalPath({
                start,
                end: pointer,
                obstacles,
            }),
        };
    }

    get isInteracting() {
        return Boolean(this.store.interaction);
    }

    get emptyLabel() {
        return _t("No nodes");
    }

    get fitLabel() {
        return _t("Fit to content");
    }

    get zoomInLabel() {
        return _t("Zoom in");
    }

    get zoomOutLabel() {
        return _t("Zoom out");
    }

    get flowLocationLabel() {
        return _t("Return to the flow");
    }

    get flowBounds() {
        if (!this.store.nodes.length) {
            return null;
        }
        const rects = this.store.nodes.map((node) => getNodeRect(node, this.props.defaultNodeSize));
        return {
            x1: Math.min(...rects.map((rect) => rect.x1)),
            y1: Math.min(...rects.map((rect) => rect.y1)),
            x2: Math.max(...rects.map((rect) => rect.x2)),
            y2: Math.max(...rects.map((rect) => rect.y2)),
        };
    }

    get flowCenter() {
        if (!this.store.nodes.length) {
            return null;
        }
        const centers = this.store.nodes.map((node) => {
            const rect = getNodeRect(node, this.props.defaultNodeSize);
            return {
                x: (rect.x1 + rect.x2) / 2,
                y: (rect.y1 + rect.y2) / 2,
            };
        });
        return {
            x: centers.reduce((sum, center) => sum + center.x, 0) / centers.length,
            y: centers.reduce((sum, center) => sum + center.y, 0) / centers.length,
        };
    }

    get connectedNodeIds() {
        const connectedNodeIds = new Set(
            this.store.nodes.filter((node) => !node.input).map((node) => node.id)
        );
        let previousSize;
        do {
            previousSize = connectedNodeIds.size;
            for (const connection of this.store.connections) {
                if (connectedNodeIds.has(connection.sourceNodeId)) {
                    connectedNodeIds.add(connection.targetNodeId);
                }
            }
        } while (connectedNodeIds.size !== previousSize);
        return connectedNodeIds;
    }

    get flowLocationIndicator() {
        const canvasEl = this.canvasRef();
        const target = this.flowCenter;
        if (!canvasEl || !target) {
            return null;
        }
        const canvasRect = canvasEl.getBoundingClientRect();
        const { x, y, scale } = this.store.viewport;
        const view = {
            x1: -x / scale,
            y1: -y / scale,
            x2: (canvasRect.width - x) / scale,
            y2: (canvasRect.height - y) / scale,
        };
        const hasVisibleNode = this.store.nodes.some((node) => {
            const rect = getNodeRect(node, this.props.defaultNodeSize);
            return (
                rect.x2 >= view.x1 && rect.x1 <= view.x2 && rect.y2 >= view.y1 && rect.y1 <= view.y2
            );
        });
        if (hasVisibleNode) {
            return null;
        }
        const viewCenter = {
            x: (view.x1 + view.x2) / 2,
            y: (view.y1 + view.y2) / 2,
        };
        const angle =
            (Math.atan2(target.y - viewCenter.y, target.x - viewCenter.x) * 180) / Math.PI + 45;
        return {
            angle,
            x: canvasRect.width / 2,
            y: canvasRect.height / 2,
        };
    }

    get flowLocationIndicatorStyle() {
        const indicator = this.flowLocationIndicator;
        return indicator
            ? `left: ${indicator.x}px; top: ${indicator.y}px; transform: translate(-50%, -50%) rotate(${indicator.angle}deg);`
            : "";
    }

    /**
     * @param {import("./flow_types").FlowNodeId} nodeId
     * @param {import("./flow_types").FlowPortId} portId
     * @returns {"valid" | "invalid" | undefined}
     */
    getPortValidation(nodeId, portId) {
        const draft = this.store.interaction?.connectionDraft;
        if (!draft) {
            return;
        }
        if (draft.reconnectSource) {
            if (draft.sourceCandidateNodeId !== nodeId || draft.sourceCandidatePortId !== portId) {
                return;
            }
            const validation = this.validateConnectionCandidate({
                id: "flow-connection-draft",
                sourceNodeId: nodeId,
                sourcePortId: portId,
                targetNodeId: draft.targetNodeId,
                targetPortId: draft.targetPortId,
            });
            return validation.valid || this.isResolvableBySourceSwap(validation)
                ? "valid"
                : "invalid";
        }
        if (draft.targetNodeId !== nodeId || draft.targetPortId !== portId) {
            return;
        }
        return this.validateConnectionCandidate({
            id: "flow-connection-draft",
            sourceNodeId: draft.sourceNodeId,
            sourcePortId: draft.sourcePortId,
            targetNodeId: nodeId,
            targetPortId: portId,
        }).valid
            ? "valid"
            : "invalid";
    }

    /**
     * @param {PointerEvent} ev
     * @returns {import("./flow_types").FlowPosition}
     */
    toWorld(ev) {
        return screenToWorld(
            { x: ev.clientX, y: ev.clientY },
            this.canvasRef().getBoundingClientRect(),
            this.store.viewport
        );
    }

    /**
     * @param {PointerEvent} ev
     */
    onCanvasPointerDown(ev) {
        if (
            (ev.button !== 0 && ev.button !== 1) ||
            ev.target.closest(
                ".o_flow_editor_node, .o_flow_editor_connection, .o_flow_editor_controls, .o_flow_editor_location_indicator"
            )
        ) {
            return;
        }
        ev.preventDefault();
        this.cancelViewportAnimation();
        this.canvasRef().focus();
        this.clearSelection();
        if (!this.store.startInteraction({ type: "pan" })) {
            return;
        }
        this.activePointerId = ev.pointerId;
        this.pointerStart = { x: ev.clientX, y: ev.clientY };
        this.panOrigin = { ...this.store.viewport };
        this.props.onPan({ phase: "start" });
    }

    /**
     * @param {Object} params
     * @param {import("./flow_types").FlowNode} params.node
     * @param {PointerEvent} params.originalEvent
     */
    onNodePointerDown({ node, originalEvent }) {
        if (originalEvent.button !== 0) {
            return;
        }
        originalEvent.preventDefault();
        originalEvent.stopPropagation();
        this.canvasRef().focus();
        const pointer = this.toWorld(originalEvent);
        if (
            !this.store.startInteraction({
                type: "node_drag",
                nodeId: node.id,
                origin: { ...node.position },
            })
        ) {
            return;
        }
        this.selectNode(node.id);
        this.activePointerId = originalEvent.pointerId;
        this.pointerStart = { x: originalEvent.clientX, y: originalEvent.clientY };
        this.dragOffset = {
            x: pointer.x - node.position.x,
            y: pointer.y - node.position.y,
        };
        this.snapNodeDrag = originalEvent.altKey;
        this.didDrag = false;
        this.props.onDrag({
            phase: "start",
            node,
            position: { ...node.position },
            originalEvent,
        });
    }

    /**
     * @param {Object} params
     * @param {import("./flow_types").FlowNodeId} params.nodeId
     * @param {import("./flow_types").FlowPort} params.port
     * @param {PointerEvent} params.originalEvent
     */
    async onPortPointerDown({ nodeId, port, originalEvent }) {
        if (originalEvent.button !== 0 || this.store.readonly || this.store.interaction) {
            return;
        }
        originalEvent.preventDefault();
        this.canvasRef().focus();
        let sourceNodeId = nodeId;
        let sourcePortId = port.id;
        let connection;
        let reconnectSource = false;
        let targetNodeId;
        let targetPortId;
        if (port.direction === "input") {
            connection = this.store.connections
                .filter(
                    (candidate) =>
                        candidate.targetNodeId === nodeId && candidate.targetPortId === port.id
                )
                .sort((connectionA, connectionB) =>
                    String(connectionA.id).localeCompare(String(connectionB.id), undefined, {
                        numeric: true,
                    })
                )
                .at(-1);
            if (connection) {
                sourceNodeId = connection.sourceNodeId;
                sourcePortId = connection.sourcePortId;
            } else {
                reconnectSource = true;
                targetNodeId = nodeId;
                targetPortId = port.id;
            }
        } else {
            connection = this.store.connections
                .filter(
                    (candidate) =>
                        candidate.sourceNodeId === nodeId && candidate.sourcePortId === port.id
                )
                .sort((connectionA, connectionB) =>
                    String(connectionA.id).localeCompare(String(connectionB.id), undefined, {
                        numeric: true,
                    })
                )
                .at(-1);
        }
        const pointer = this.toWorld(originalEvent);
        if (
            !this.store.startInteraction({
                type: "connection_drag",
                connectionDraft: {
                    sourceNodeId,
                    sourcePortId,
                    pointer,
                    ...(reconnectSource
                        ? {
                              reconnectSource: true,
                              targetNodeId,
                              targetPortId,
                          }
                        : {}),
                },
            })
        ) {
            return;
        }
        this.activePointerId = originalEvent.pointerId;
        if (connection) {
            let disconnectResult = this.props.onDisconnect({ connection });
            if (disconnectResult?.then) {
                disconnectResult = await disconnectResult;
            }
            if (disconnectResult === false) {
                this.store.cancelInteraction();
                this.resetPointerState();
                return;
            }
            this.store.removeConnection(connection.id);
        }
    }

    /**
     * @param {Object} params
     * @param {import("./flow_types").FlowNode} params.node
     * @param {PointerEvent} params.originalEvent
     */
    onResizePointerDown({ node, originalEvent }) {
        if (originalEvent.button !== 0 || node.shape === "circle") {
            return;
        }
        originalEvent.preventDefault();
        this.canvasRef().focus();
        const size = getNodeSize(node, this.props.defaultNodeSize);
        if (
            !this.store.startInteraction({
                type: "node_resize",
                nodeId: node.id,
                origin: { ...size },
            })
        ) {
            return;
        }
        this.selectNode(node.id);
        this.activePointerId = originalEvent.pointerId;
        this.pointerStart = { x: originalEvent.clientX, y: originalEvent.clientY };
        this.props.onResize({
            phase: "start",
            node,
            size: { ...size },
            originalEvent,
        });
    }

    /**
     * @param {PointerEvent} ev
     */
    onPointerMove(ev) {
        if (ev.pointerId !== this.activePointerId || !this.store.interaction) {
            return;
        }
        ev.preventDefault();
        if (this.store.interaction.type === "node_drag") {
            const pointer = this.toWorld(ev);
            const position = {
                x: pointer.x - this.dragOffset.x,
                y: pointer.y - this.dragOffset.y,
            };
            if (this.snapNodeDrag) {
                const gridSize = Math.max(this.props.gridSize, 1);
                position.x = Math.round(position.x / gridSize) * gridSize;
                position.y = Math.round(position.y / gridSize) * gridSize;
            }
            this.didDrag ||=
                Math.hypot(ev.clientX - this.pointerStart.x, ev.clientY - this.pointerStart.y) > 3;
            if (this.store.moveNode(this.store.interaction.nodeId, position)) {
                this.props.onDrag({
                    phase: "move",
                    node: this.store.getNode(this.store.interaction.nodeId),
                    position,
                    originalEvent: ev,
                });
            }
        } else if (this.store.interaction.type === "node_resize") {
            const { nodeId, origin } = this.store.interaction;
            const scale = this.store.viewport.scale;
            const size = {
                width: Math.max(
                    this.props.minNodeSize.width,
                    origin.width + (ev.clientX - this.pointerStart.x) / scale
                ),
                height: Math.max(
                    this.props.minNodeSize.height,
                    origin.height + (ev.clientY - this.pointerStart.y) / scale
                ),
            };
            if (this.store.resizeNode(nodeId, size)) {
                this.props.onResize({
                    phase: "move",
                    node: this.store.getNode(nodeId),
                    size,
                    originalEvent: ev,
                });
            }
        } else if (this.store.interaction.type === "connection_drag") {
            const target = this.store.interaction.connectionDraft.reconnectSource
                ? this.getOutputPortAtPoint(ev.clientX, ev.clientY)
                : this.getInputPortAtPoint(ev.clientX, ev.clientY);
            this.store.updateConnectionDraft(
                this.toWorld(ev),
                target
                    ? {
                          nodeId: target.node.id,
                          portId: target.portId,
                      }
                    : undefined
            );
        } else {
            this.setViewport({
                x: this.panOrigin.x + ev.clientX - this.pointerStart.x,
                y: this.panOrigin.y + ev.clientY - this.pointerStart.y,
            });
        }
    }

    /**
     * @param {PointerEvent} ev
     */
    async onPointerUp(ev) {
        if (ev.pointerId !== this.activePointerId || !this.store.interaction) {
            return;
        }
        const interaction = this.store.interaction;
        if (interaction.type === "node_drag") {
            const node = this.store.getNode(interaction.nodeId);
            this.props.onDrag({
                phase: "end",
                node,
                position: { ...node.position },
                originalEvent: ev,
            });
            this.suppressNodeClick = this.didDrag;
            this.store.endInteraction();
        } else if (interaction.type === "node_resize") {
            const node = this.store.getNode(interaction.nodeId);
            this.props.onResize({
                phase: "end",
                node,
                size: { ...node.size },
                originalEvent: ev,
            });
            this.store.endInteraction();
        } else if (interaction.type === "connection_drag") {
            // A self-connection's source and target ports share the same
            // node <article>, so the browser's own click-target resolution
            // (nearest common ancestor of pointerdown/pointerup) synthesizes
            // a click on that node once released - the ports' own click
            // handlers stop propagation, but aren't in that click's path.
            // Connecting two different nodes never hits this: their common
            // ancestor sits above any element with a click handler.
            this.suppressNodeClick = true;
            try {
                await this.connectToPortAtPointer(interaction.connectionDraft, ev);
            } finally {
                this.store.endInteraction();
                this.resetPointerState();
            }
            return;
        } else {
            this.store.endInteraction();
            if (interaction.type === "pan") {
                this.props.onPan({ phase: "end" });
            }
        }
        this.resetPointerState();
    }

    /**
     * @param {PointerEvent} ev
     */
    onPointerCancel(ev) {
        if (ev.pointerId !== this.activePointerId || !this.store.interaction) {
            return;
        }
        const interaction = this.store.interaction;
        this.store.cancelInteraction();
        if (interaction.type === "node_drag") {
            this.props.onDrag({
                phase: "cancel",
                node: this.store.getNode(interaction.nodeId),
                position: { ...interaction.origin },
                originalEvent: ev.originalEvent || ev,
            });
        } else if (interaction.type === "node_resize") {
            this.props.onResize({
                phase: "cancel",
                node: this.store.getNode(interaction.nodeId),
                size: { ...interaction.origin },
                originalEvent: ev.originalEvent || ev,
            });
        } else if (interaction.type === "pan") {
            this.props.onPan({ phase: "cancel" });
        }
        this.resetPointerState();
    }

    /**
     * @param {import("./flow_types").FlowConnectionDraft} draft
     * @param {PointerEvent} ev
     */
    async connectToPortAtPointer(draft, ev) {
        if (draft.reconnectSource) {
            const source = this.getOutputPortAtPoint(ev.clientX, ev.clientY);
            if (source) {
                await this.connectPorts(
                    {
                        sourceNodeId: source.node.id,
                        sourcePortId: source.portId,
                    },
                    {
                        node: this.store.getNode(draft.targetNodeId),
                        portId: draft.targetPortId,
                    }
                );
            }
            return;
        }
        const target = this.getInputPortAtPoint(ev.clientX, ev.clientY);
        if (!target) {
            return;
        }
        await this.connectPorts(draft, target);
    }

    /**
     * @param {import("./flow_types").FlowConnectionDraft} draft
     * @param {{ node: import("./flow_types").FlowNode, portId: import("./flow_types").FlowPortId }} target
     */
    async connectPorts(draft, target) {
        const connection = {
            id: this.store.getNextConnectionId(),
            sourceNodeId: draft.sourceNodeId,
            sourcePortId: draft.sourcePortId,
            targetNodeId: target.node.id,
            targetPortId: target.portId,
        };
        let validation = this.validateConnectionCandidate(connection);
        if (!validation.valid && this.isResolvableBySourceSwap(validation)) {
            if (!(await this.freeUpSourcePort(connection))) {
                return;
            }
            validation = this.validateConnectionCandidate(connection);
        }
        if (!validation.valid) {
            this.props.onConnectionRejected({ connection, validation });
            return;
        }
        const result = await this.props.onConnect(connection);
        if (result !== false) {
            const persistedConnection = result && typeof result === "object" ? result : connection;
            if (this.store.getConnection(persistedConnection.id)) {
                // The consumer's onConnect already fed the new connection back
                // through props (and onWillUpdateProps synced it into the
                // store) before this async call resumed - nothing left to do.
                return;
            }
            const persistedValidation = this.validateConnectionCandidate(persistedConnection);
            if (persistedValidation.valid) {
                this.store.addConnection(persistedConnection);
            } else {
                this.props.onConnectionRejected({
                    connection: persistedConnection,
                    validation: persistedValidation,
                });
            }
        }
    }

    /**
     * A failed validation is resolvable by disconnecting whatever already
     * occupies the candidate's source port.
     *
     * @param {import("./connection_validator").FlowConnectionValidation} validation
     * @returns {boolean}
     */
    isResolvableBySourceSwap(validation) {
        return validation.reason === "source_saturated";
    }

    /**
     * Disconnect whatever already occupies a connection candidate's source
     * port, so it can be reused instead of rejecting the new connection.
     *
     * @param {import("./flow_types").FlowConnection} connection
     * @returns {Promise<boolean>} false if a consumer vetoed a disconnection
     */
    async freeUpSourcePort(connection) {
        const displaced = this.store.connections.filter(
            (candidate) =>
                candidate.sourceNodeId === connection.sourceNodeId &&
                candidate.sourcePortId === connection.sourcePortId
        );
        for (const removed of displaced) {
            let disconnectResult = this.props.onDisconnect({ connection: removed });
            if (disconnectResult?.then) {
                disconnectResult = await disconnectResult;
            }
            if (disconnectResult === false) {
                return false;
            }
            this.store.removeConnection(removed.id);
        }
        return true;
    }

    /**
     * @param {number} clientX
     * @param {number} clientY
     * @returns {{ node: import("./flow_types").FlowNode, portId: import("./flow_types").FlowPortId } | null}
     */
    getInputPortAtPoint(clientX, clientY) {
        const portEl = document
            .elementFromPoint(clientX, clientY)
            ?.closest(".o_flow_editor_port_input");
        if (!portEl || !this.canvasRef().contains(portEl)) {
            return null;
        }
        const node = this.store.nodes.find(
            (candidate) => String(candidate.id) === portEl.dataset.nodeId
        );
        if (!node || node.input?.id !== portEl.dataset.portId) {
            return null;
        }
        return { node, portId: portEl.dataset.portId };
    }

    /**
     * @param {number} clientX
     * @param {number} clientY
     * @returns {{ node: import("./flow_types").FlowNode, portId: import("./flow_types").FlowPortId } | null}
     */
    getOutputPortAtPoint(clientX, clientY) {
        const portEl = document
            .elementFromPoint(clientX, clientY)
            ?.closest(".o_flow_editor_port_output");
        if (!portEl || !this.canvasRef().contains(portEl)) {
            return null;
        }
        const node = this.store.nodes.find(
            (candidate) => String(candidate.id) === portEl.dataset.nodeId
        );
        if (!node?.outputs.some((output) => output.id === portEl.dataset.portId)) {
            return null;
        }
        return { node, portId: portEl.dataset.portId };
    }

    /**
     * Apply structural rules before delegating domain-specific rules.
     *
     * `canConnect` must be synchronous because it also drives hover feedback.
     *
     * @param {import("./flow_types").FlowConnection} connection
     * @returns {import("./connection_validator").FlowConnectionValidation}
     */
    validateConnectionCandidate(connection) {
        const validation = validateConnection(connection, {
            nodes: this.store.nodes,
            connections: this.store.connections,
            allowSelfConnections: this.props.allowSelfConnections,
        });
        if (!validation.valid) {
            return validation;
        }
        return normalizeConnectionValidation(this.props.canConnect(connection));
    }

    /**
     * @param {WheelEvent} ev
     */
    onWheel(ev) {
        if (!ev.ctrlKey && !ev.metaKey) {
            return;
        }
        ev.preventDefault();
        this.cancelViewportAnimation();
        const canvasRect = this.canvasRef().getBoundingClientRect();
        const pointer = screenToWorld(
            { x: ev.clientX, y: ev.clientY },
            canvasRect,
            this.store.viewport
        );
        const scale = clampScale(this.store.viewport.scale * (ev.deltaY > 0 ? 0.9 : 1.1));
        this.setViewport({
            x: ev.clientX - canvasRect.left - pointer.x * scale,
            y: ev.clientY - canvasRect.top - pointer.y * scale,
            scale,
        });
    }

    /**
     * @param {number} factor
     */
    zoomBy(factor) {
        this.cancelViewportAnimation();
        const canvasRect = this.canvasRef().getBoundingClientRect();
        const center = {
            x: canvasRect.left + canvasRect.width / 2,
            y: canvasRect.top + canvasRect.height / 2,
        };
        const worldCenter = screenToWorld(center, canvasRect, this.store.viewport);
        const scale = clampScale(this.store.viewport.scale * factor);
        this.setViewport({
            x: canvasRect.width / 2 - worldCenter.x * scale,
            y: canvasRect.height / 2 - worldCenter.y * scale,
            scale,
        });
    }

    zoomIn() {
        this.zoomBy(1.1);
    }

    zoomOut() {
        this.zoomBy(0.9);
    }

    fitToContent() {
        this.cancelViewportAnimation();
        const canvasRect = this.canvasRef().getBoundingClientRect();
        if (!this.store.nodes.length || !canvasRect.width || !canvasRect.height) {
            this.setViewport({ x: 0, y: 0, scale: 1 });
            return;
        }
        const bounds = this.flowBounds;
        const padding = 48;
        const width = Math.max(bounds.x2 - bounds.x1, 1);
        const height = Math.max(bounds.y2 - bounds.y1, 1);
        const scale = clampScale(
            Math.min(
                (canvasRect.width - padding * 2) / width,
                (canvasRect.height - padding * 2) / height,
                1
            )
        );
        this.setViewport({
            x: (canvasRect.width - width * scale) / 2 - bounds.x1 * scale,
            y: (canvasRect.height - height * scale) / 2 - bounds.y1 * scale,
            scale,
        });
    }

    onFlowLocationClick(ev) {
        ev.stopPropagation();
        const target = this.flowCenter;
        const canvasEl = this.canvasRef();
        if (!target || !canvasEl) {
            return;
        }
        const canvasRect = canvasEl.getBoundingClientRect();
        const scale = this.store.viewport.scale;
        this.animateViewportTo({
            x: canvasRect.width / 2 - target.x * scale,
            y: canvasRect.height / 2 - target.y * scale,
        });
    }

    /**
     * Animate viewport translation so the directional indicator has a clear outcome.
     *
     * @param {{ x: number, y: number }} target
     * @param {number} [duration]
     */
    animateViewportTo(target, duration = 400) {
        this.cancelViewportAnimation();
        const start = { ...this.store.viewport };
        const delta = {
            x: target.x - start.x,
            y: target.y - start.y,
        };
        let startTime;
        const step = (timestamp) => {
            startTime ??= timestamp;
            const progress = Math.min(1, (timestamp - startTime) / duration);
            const eased = progress < 0.5 ? 2 * progress ** 2 : 1 - (-2 * progress + 2) ** 2 / 2;
            this.setViewport({
                x: start.x + delta.x * eased,
                y: start.y + delta.y * eased,
            });
            if (progress < 1) {
                this.viewportAnimationFrame = requestAnimationFrame(step);
            } else {
                this.viewportAnimationFrame = null;
            }
        };
        this.viewportAnimationFrame = requestAnimationFrame(step);
    }

    cancelViewportAnimation() {
        if (this.viewportAnimationFrame) {
            cancelAnimationFrame(this.viewportAnimationFrame);
            this.viewportAnimationFrame = null;
        }
    }

    /**
     * @param {Partial<import("./flow_types").FlowViewport>} values
     */
    setViewport(values) {
        this.store.setViewport(values);
        this.props.onViewportChange({ ...this.store.viewport });
    }

    /**
     * @param {import("./flow_types").FlowNode} node
     * @param {Event} originalEvent
     */
    onNodeClick({ node, originalEvent }) {
        if (this.suppressNodeClick) {
            this.suppressNodeClick = false;
            return;
        }
        this.selectNode(node.id);
        this.props.onNodeClick({ node, originalEvent });
    }

    /**
     * @param {Object} params
     * @param {import("./flow_types").FlowConnectionId} params.connectionId
     */
    onConnectionClick({ connectionId }) {
        this.canvasRef().focus();
        this.store.setSelection({ connectionIds: [connectionId] });
        this.notifySelectionChange();
    }

    /**
     * @param {import("./flow_types").FlowNodeId} nodeId
     */
    selectNode(nodeId) {
        this.store.setSelection({ nodeIds: [nodeId] });
        this.notifySelectionChange();
    }

    clearSelection() {
        this.store.clearSelection();
        this.notifySelectionChange();
    }

    notifySelectionChange() {
        this.props.onSelectionChange({
            nodeIds: [...this.store.selection.nodeIds],
            connectionIds: [...this.store.selection.connectionIds],
        });
    }

    async onNodeDeleteClick({ node }) {
        if (await this.deleteNode(node)) {
            this.notifySelectionChange();
        }
    }

    async deleteNode(node) {
        if (
            !node ||
            node.readonly ||
            node.deletable === false ||
            (await this.props.onNodeDelete({ node })) === false
        ) {
            return false;
        }
        const attachedConnections = this.store.connections.filter(
            (connection) =>
                connection.sourceNodeId === node.id || connection.targetNodeId === node.id
        );
        for (const connection of attachedConnections) {
            if ((await this.props.onDisconnect({ connection })) === false) {
                return false;
            }
        }
        return this.store.removeNode(node.id);
    }

    /**
     * @param {KeyboardEvent} ev
     */
    async onKeyDown(ev) {
        if (!this.canvasRef()?.contains(document.activeElement)) {
            return;
        }
        if (ev.key === "Escape" && this.store.interaction) {
            ev.preventDefault();
            this.onPointerCancel({
                pointerId: this.activePointerId,
                originalEvent: ev,
            });
            return;
        }
        if (
            this.store.readonly ||
            (ev.key !== "Delete" && ev.key !== "Backspace") ||
            ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)
        ) {
            return;
        }
        ev.preventDefault();
        for (const connectionId of [...this.store.selection.connectionIds]) {
            const connection = this.store.getConnection(connectionId);
            if (connection && (await this.props.onDisconnect({ connection })) !== false) {
                this.store.removeConnection(connectionId);
            }
        }
        for (const nodeId of [...this.store.selection.nodeIds]) {
            const node = this.store.getNode(nodeId);
            await this.deleteNode(node);
        }
        this.notifySelectionChange();
    }

    resetPointerState() {
        this.activePointerId = null;
        this.pointerStart = null;
        this.panOrigin = null;
        this.dragOffset = null;
        this.didDrag = false;
        this.snapNodeDrag = false;
    }

    /**
     * @param {import("./flow_types").FlowNodeId} nodeId
     * @returns {boolean}
     */
    isNodeSelected(nodeId) {
        return this.store.selection.nodeIds.includes(nodeId);
    }

    /**
     * @param {import("./flow_types").FlowConnectionId} connectionId
     * @returns {boolean}
     */
    isConnectionSelected(connectionId) {
        return this.store.selection.connectionIds.includes(connectionId);
    }
}
