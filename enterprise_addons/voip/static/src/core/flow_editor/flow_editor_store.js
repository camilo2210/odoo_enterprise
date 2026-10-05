import { proxy } from "@odoo/owl";

import { DEFAULT_FLOW_VIEWPORT } from "./flow_types";
import { clampScale } from "./geometry/coordinates";

/**
 * Copy the editor-owned parts of a node so that interactions never mutate
 * objects supplied by a consumer. Arbitrary `data` payloads remain
 * consumer-owned and must be treated as read-only by the editor.
 *
 * @param {import("./flow_types").FlowNode} node
 * @returns {import("./flow_types").FlowNode}
 */
function copyNode(node) {
    return {
        ...node,
        position: { ...node.position },
        ...(node.size ? { size: { ...node.size } } : {}),
        ...(node.record ? { record: { ...node.record, data: { ...node.record.data } } } : {}),
        ...(node.input ? { input: { ...node.input } } : {}),
        outputs: node.outputs.map((output) => ({ ...output })),
    };
}

/**
 * Local reactive state for a flow editor.
 *
 * Consumers own loading and persistence. The store only owns the graph copy and
 * ephemeral UI state used while editing it.
 */
export class FlowEditorStore {
    /**
     * @param {Object} [params]
     * @param {import("./flow_types").FlowNode[]} [params.nodes]
     * @param {import("./flow_types").FlowConnection[]} [params.connections]
     * @param {import("./flow_types").FlowViewport} [params.viewport]
     * @param {boolean} [params.readonly]
     */
    constructor({
        nodes = [],
        connections = [],
        viewport = DEFAULT_FLOW_VIEWPORT,
        readonly = false,
    } = {}) {
        this.nodes = nodes.map(copyNode);
        this.connections = connections.map((connection) => ({ ...connection }));
        this.viewport = {
            x: viewport.x,
            y: viewport.y,
            scale: clampScale(viewport.scale),
        };
        this.selection = {
            nodeIds: [],
            connectionIds: [],
        };
        this.interaction = null;
        this.readonly = readonly;
        this.connectionSequence = 1;
    }

    /**
     * Replace consumer-owned graph data while preserving the viewport.
     *
     * @param {Object} graph
     * @param {import("./flow_types").FlowNode[]} graph.nodes
     * @param {import("./flow_types").FlowConnection[]} graph.connections
     */
    setGraph({ nodes, connections }) {
        const interaction = this.interaction;
        this.nodes = nodes.map(copyNode);
        this.connections = connections.map((connection) => ({ ...connection }));
        this._removeMissingItemsFromSelection();
        const sourceNode =
            interaction?.type === "connection_drag"
                ? this.getNode(interaction.connectionDraft.sourceNodeId)
                : null;
        const sourcePortExists = sourceNode?.outputs.some(
            (port) => port.id === interaction.connectionDraft.sourcePortId
        );
        // Rewiring a connection updates consumer props while the pointer gesture is active.
        this.interaction = sourcePortExists ? interaction : null;
    }

    /**
     * @param {import("./flow_types").FlowNodeId} nodeId
     * @returns {import("./flow_types").FlowNode | undefined}
     */
    getNode(nodeId) {
        return this.nodes.find((node) => node.id === nodeId);
    }

    /**
     * @param {import("./flow_types").FlowConnectionId} connectionId
     * @returns {import("./flow_types").FlowConnection | undefined}
     */
    getConnection(connectionId) {
        return this.connections.find((connection) => connection.id === connectionId);
    }

    getNextConnectionId() {
        let connectionId;
        do {
            connectionId = `flow-connection-${this.connectionSequence++}`;
        } while (this.getConnection(connectionId));
        return connectionId;
    }

    /**
     * @param {import("./flow_types").FlowNode} node
     * @returns {boolean}
     */
    addNode(node) {
        if (this.readonly || this.getNode(node.id)) {
            return false;
        }
        this.nodes.push(copyNode(node));
        return true;
    }

    /**
     * @param {import("./flow_types").FlowNodeId} nodeId
     * @param {Partial<import("./flow_types").FlowNode>} values
     * @returns {boolean}
     */
    updateNode(nodeId, values) {
        const nodeIndex = this.nodes.findIndex((node) => node.id === nodeId);
        const node = this.nodes[nodeIndex];
        if (this.readonly || !node || node.readonly) {
            return false;
        }
        this.nodes[nodeIndex] = copyNode({
            ...node,
            ...values,
            position: values.position || node.position,
            input: Object.hasOwn(values, "input") ? values.input : node.input,
            outputs: values.outputs || node.outputs,
        });
        return true;
    }

    /**
     * @param {import("./flow_types").FlowNodeId} nodeId
     * @param {import("./flow_types").FlowPosition} position
     * @returns {boolean}
     */
    moveNode(nodeId, position) {
        return this.updateNode(nodeId, { position });
    }

    /**
     * @param {import("./flow_types").FlowNodeId} nodeId
     * @param {import("./flow_types").FlowSize} size
     * @returns {boolean}
     */
    resizeNode(nodeId, size) {
        return this.updateNode(nodeId, { size });
    }

    /**
     * Removing a node also removes every connection attached to it.
     *
     * @param {import("./flow_types").FlowNodeId} nodeId
     * @returns {boolean}
     */
    removeNode(nodeId) {
        const node = this.getNode(nodeId);
        if (this.readonly || !node || node.readonly || node.deletable === false) {
            return false;
        }
        this.nodes = this.nodes.filter((candidate) => candidate.id !== nodeId);
        this.connections = this.connections.filter(
            (connection) => connection.sourceNodeId !== nodeId && connection.targetNodeId !== nodeId
        );
        this._removeMissingItemsFromSelection();
        return true;
    }

    /**
     * @param {import("./flow_types").FlowConnection} connection
     * @returns {boolean}
     */
    addConnection(connection) {
        if (this.readonly || this.getConnection(connection.id)) {
            return false;
        }
        this.connections.push({ ...connection });
        return true;
    }

    /**
     * @param {import("./flow_types").FlowConnectionId} connectionId
     * @returns {boolean}
     */
    removeConnection(connectionId) {
        if (this.readonly || !this.getConnection(connectionId)) {
            return false;
        }
        this.connections = this.connections.filter((connection) => connection.id !== connectionId);
        this._removeMissingItemsFromSelection();
        return true;
    }

    /**
     * @param {Partial<import("./flow_types").FlowSelection>} selection
     */
    setSelection({ nodeIds = [], connectionIds = [] }) {
        const availableNodeIds = new Set(this.nodes.map((node) => node.id));
        const availableConnectionIds = new Set(this.connections.map((connection) => connection.id));
        this.selection.nodeIds = [...new Set(nodeIds)].filter((id) => availableNodeIds.has(id));
        this.selection.connectionIds = [...new Set(connectionIds)].filter((id) =>
            availableConnectionIds.has(id)
        );
    }

    clearSelection() {
        this.selection.nodeIds = [];
        this.selection.connectionIds = [];
    }

    /**
     * @param {Partial<import("./flow_types").FlowViewport>} values
     */
    setViewport(values) {
        this.viewport = {
            ...this.viewport,
            ...values,
            scale: clampScale(values.scale ?? this.viewport.scale),
        };
    }

    /**
     * @param {boolean} readonly
     */
    setReadonly(readonly) {
        if (readonly && this.interaction?.type !== "pan") {
            this.cancelInteraction();
        }
        this.readonly = readonly;
    }

    /**
     * @param {import("./flow_types").FlowInteraction} interaction
     * @returns {boolean}
     */
    startInteraction(interaction) {
        if (this.interaction || (this.readonly && interaction.type !== "pan")) {
            return false;
        }
        if (interaction.type === "node_drag" || interaction.type === "node_resize") {
            const node = this.getNode(interaction.nodeId);
            if (!node || node.readonly) {
                return false;
            }
            this.interaction = {
                ...interaction,
                origin: { ...interaction.origin },
            };
        } else if (interaction.type === "connection_drag") {
            this.interaction = {
                ...interaction,
                connectionDraft: {
                    ...interaction.connectionDraft,
                    pointer: { ...interaction.connectionDraft.pointer },
                },
            };
        } else {
            this.interaction = { ...interaction };
        }
        return true;
    }

    /**
     * @param {import("./flow_types").FlowPosition} pointer
     * @param {Object} [target]
     * @param {import("./flow_types").FlowNodeId} [target.nodeId]
     * @param {import("./flow_types").FlowPortId} [target.portId]
     */
    updateConnectionDraft(pointer, target = {}) {
        if (this.interaction?.type === "connection_drag") {
            const draft = this.interaction.connectionDraft;
            Object.assign(
                draft,
                draft.reconnectSource
                    ? {
                          pointer,
                          sourceCandidateNodeId: target.nodeId,
                          sourceCandidatePortId: target.portId,
                      }
                    : {
                          pointer,
                          targetNodeId: target.nodeId,
                          targetPortId: target.portId,
                      }
            );
        }
    }

    endInteraction() {
        this.interaction = null;
    }

    cancelInteraction() {
        if (this.interaction?.type === "node_drag") {
            this.moveNode(this.interaction.nodeId, this.interaction.origin);
        } else if (this.interaction?.type === "node_resize") {
            this.resizeNode(this.interaction.nodeId, this.interaction.origin);
        }
        this.interaction = null;
    }

    _removeMissingItemsFromSelection() {
        const nodeIds = new Set(this.nodes.map((node) => node.id));
        const connectionIds = new Set(this.connections.map((connection) => connection.id));
        this.selection.nodeIds = this.selection.nodeIds.filter((id) => nodeIds.has(id));
        this.selection.connectionIds = this.selection.connectionIds.filter((id) =>
            connectionIds.has(id)
        );
    }
}

/**
 * Create an Owl 3 reactive flow editor store.
 *
 * @param {ConstructorParameters<typeof FlowEditorStore>[0]} [params]
 * @returns {FlowEditorStore}
 */
export function createFlowEditorStore(params) {
    return proxy(new FlowEditorStore(params));
}
