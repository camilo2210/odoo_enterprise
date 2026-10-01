/**
 * Registry owned by a flow editor consumer.
 *
 * The generic canvas only renders nodes. Type factories, uniqueness and
 * business defaults belong to the adapter that creates those nodes.
 */
export class FlowNodeTypeRegistry {
    constructor() {
        this.categories = new Map();
        this.definitions = new Map();
    }

    /**
     * @param {string} id
     * @param {Object} category
     * @param {string} category.label
     * @param {number} [category.sequence]
     */
    addCategory(id, category) {
        if (this.categories.has(id)) {
            throw new Error(`Flow node category "${id}" is already registered.`);
        }
        if (!category.label) {
            throw new Error(`Flow node category "${id}" requires a label.`);
        }
        this.categories.set(id, Object.freeze({ id, sequence: 100, ...category }));
    }

    /**
     * @param {string} type
     * @param {Object} definition
     * @param {typeof import("@odoo/owl").Component} [definition.Component]
     * @param {typeof import("@odoo/owl").Component} [definition.ConfigComponent]
     * @param {string} definition.category
     * @param {string} definition.description
     * @param {string} definition.label
     * @param {string} [definition.icon]
     * @param {string} [definition.icon_class]
     * @param {boolean} [definition.palette]
     * @param {number} [definition.sequence]
     * @param {import("../core/flow_editor/flow_types").FlowSize} definition.size
     * @param {"rectangle" | "circle"} [definition.shape]
     * @param {boolean} [definition.terminal]
     * @param {boolean} [definition.unique]
     * @param {(node: import("../core/flow_editor/flow_types").FlowNode) => true | string} [definition.validate]
     * @param {(params: Object) => import("../core/flow_editor/flow_types").FlowNode} definition.create
     */
    add(type, definition) {
        if (this.definitions.has(type)) {
            throw new Error(`Flow node type "${type}" is already registered.`);
        }
        if (
            !definition.label ||
            !definition.description ||
            !this.categories.has(definition.category) ||
            !definition.size ||
            (definition.Component && typeof definition.Component !== "function") ||
            (definition.ConfigComponent && typeof definition.ConfigComponent !== "function") ||
            typeof definition.create !== "function"
        ) {
            throw new Error(
                `Flow node type "${type}" requires a category, a label, a description, a size and a create function.`
            );
        }
        this.definitions.set(
            type,
            Object.freeze({
                type,
                palette: true,
                sequence: 100,
                unique: false,
                ...definition,
            })
        );
    }

    /**
     * @param {string} type
     * @returns {Object}
     */
    get(type) {
        const definition = this.definitions.get(type);
        if (!definition) {
            throw new Error(`Unknown flow node type "${type}".`);
        }
        return definition;
    }

    /**
     * @returns {Object[]}
     */
    getAll() {
        return [...this.definitions.values()].sort(
            (definitionA, definitionB) => definitionA.sequence - definitionB.sequence
        );
    }

    /**
     * @param {import("../core/flow_editor/flow_types").FlowNode} node
     * @returns {typeof import("@odoo/owl").Component | undefined}
     */
    getNodeComponent(node) {
        return this.definitions.get(node.type)?.Component;
    }

    /**
     * @param {import("../core/flow_editor/flow_types").FlowNode} node
     * @returns {Object | undefined}
     */
    getNodeConfiguration(node) {
        const definition = this.definitions.get(node.type);
        return definition?.ConfigComponent ? definition : undefined;
    }

    /**
     * @returns {Object[]}
     */
    getCategories() {
        return [...this.categories.values()].sort(
            (categoryA, categoryB) => categoryA.sequence - categoryB.sequence
        );
    }

    /**
     * @param {string} type
     * @param {import("../core/flow_editor/flow_types").FlowNode[]} nodes
     * @returns {boolean}
     */
    canCreate(type, nodes) {
        const definition = this.get(type);
        return !definition.unique || !nodes.some((node) => node.type === type);
    }

    /**
     * @param {string} type
     * @param {Object} params
     * @param {import("../core/flow_editor/flow_types").FlowNode[]} [params.nodes]
     * @returns {import("../core/flow_editor/flow_types").FlowNode}
     */
    create(type, { nodes = [], ...params } = {}) {
        const definition = this.get(type);
        if (!this.canCreate(type, nodes)) {
            throw new Error(`Unique flow node type "${type}" already exists.`);
        }
        return definition.create(params);
    }
}

export const flowNodeTypeRegistry = new FlowNodeTypeRegistry();
