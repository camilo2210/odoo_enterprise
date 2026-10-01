/**
 * @typedef {string | number} FlowNodeId
 */

/**
 * @typedef {string | number} FlowConnectionId
 */

/**
 * @typedef {string} FlowPortId
 */

/**
 * Position in the flow editor's world coordinates.
 *
 * @typedef FlowPosition
 * @property {number} x
 * @property {number} y
 */

/**
 * @typedef FlowSize
 * @property {number} width
 * @property {number} height
 */

/**
 * Translation and zoom applied to the flow world.
 *
 * @typedef FlowViewport
 * @property {number} x
 * @property {number} y
 * @property {number} scale
 */

/**
 * Reference to any persisted Odoo record represented by a node.
 *
 * `data` is an optional snapshot used for display. The record reference remains
 * the source of identity and consumers decide how the record is loaded or edited.
 *
 * @typedef FlowRecord
 * @property {string} resModel
 * @property {number} resId
 * @property {Record<string, unknown>} [data]
 */

/**
 * @typedef {"input" | "output"} FlowPortDirection
 */

/**
 * A connection endpoint exposed by a node.
 *
 * Compatibility and cardinality are declarative so consumers can describe
 * domain-specific ports without coupling the editor to their business models.
 *
 * @typedef FlowPort
 * @property {FlowPortId} id
 * @property {FlowPortDirection} direction
 * @property {string} [label]
 * @property {string[]} [accepts]
 * @property {string} [provides]
 * @property {number} [maxConnections]
 * @property {Record<string, unknown>} [data]
 */

/**
 * A node displayed by the flow editor.
 *
 * `record` can point to any Odoo model, such as `res.partner` or `res.users`.
 * Nodes without a persisted record are also supported.
 *
 * @typedef FlowNode
 * @property {FlowNodeId} id
 * @property {string} type
 * @property {FlowPosition} position
 * @property {FlowSize} [size]
 * @property {"rectangle" | "circle"} [shape]
 * @property {number} [headerHeight]
 * @property {FlowRecord} [record]
 * @property {FlowPort} [input]
 * @property {FlowPort[]} outputs
 * @property {Record<string, unknown>} [data]
 * @property {boolean} [readonly]
 * @property {boolean} [deletable]
 */

/**
 * @typedef FlowSelection
 * @property {FlowNodeId[]} nodeIds
 * @property {FlowConnectionId[]} connectionIds
 */

/**
 * @typedef FlowConnectionDraft
 * @property {FlowNodeId} sourceNodeId
 * @property {FlowPortId} sourcePortId
 * @property {FlowPosition} pointer
 * @property {boolean} [reconnectSource]
 * @property {FlowNodeId} [sourceCandidateNodeId]
 * @property {FlowPortId} [sourceCandidatePortId]
 * @property {FlowNodeId} [targetNodeId]
 * @property {FlowPortId} [targetPortId]
 */

/**
 * @typedef {{
 *     type: "node_drag",
 *     nodeId: FlowNodeId,
 *     origin: FlowPosition,
 * } | {
 *     type: "node_resize",
 *     nodeId: FlowNodeId,
 *     origin: FlowSize,
 * } | {
 *     type: "connection_drag",
 *     connectionDraft: FlowConnectionDraft,
 * } | {
 *     type: "pan",
 * }} FlowInteraction
 */

/**
 * A directed connection between an output port and an input port.
 *
 * @typedef FlowConnection
 * @property {FlowConnectionId} id
 * @property {FlowNodeId} sourceNodeId
 * @property {FlowPortId} sourcePortId
 * @property {FlowNodeId} targetNodeId
 * @property {FlowPortId} targetPortId
 * @property {Record<string, unknown>} [data]
 */

export const DEFAULT_FLOW_VIEWPORT = Object.freeze({ x: 0, y: 0, scale: 1 });
