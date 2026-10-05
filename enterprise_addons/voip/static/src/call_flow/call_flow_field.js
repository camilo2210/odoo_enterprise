import { Component, onMounted, proxy, signal, useOnChange, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { CharField } from "@web/views/fields/char/char_field";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

import { FlowEditor } from "@voip/core/flow_editor/flow_editor";
import { screenToWorld } from "@voip/core/flow_editor/geometry/coordinates";
import { FlowNodeConfigurationDialog } from "@voip/flow_editor/flow_node_configuration_dialog";
import { FlowNodePalette } from "@voip/flow_editor/flow_node_palette";
import { flowNodeTypeRegistry } from "@voip/flow_editor/node_types";
import {
    RECORD_CONFIGS,
    setTerminalRecordNode,
} from "@voip/flow_editor/node_types/terminal_record_flow_node";

function copyNode(node) {
    if (["hangup", "start"].includes(node.type)) {
        return flowNodeTypeRegistry.create(node.type, {
            id: node.id,
            position: { ...node.position },
        });
    }
    return {
        ...node,
        position: { ...node.position },
        ...(node.size ? { size: { ...node.size } } : {}),
        ...(node.record ? { record: { ...node.record, data: { ...node.record.data } } } : {}),
        ...(node.input ? { input: { ...node.input } } : {}),
        outputs: node.outputs.map((output) => ({ ...output })),
        data: { ...node.data },
    };
}

export class CallFlowField extends Component {
    static template = "voip.CallFlowField";
    static components = { CharField, FlowEditor, FlowNodePalette };

    props = useProps(standardFieldProps);
    registry = flowNodeTypeRegistry;
    canvasRef = signal.ref();

    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.orm = useService("orm");
        const graphData = this.props.record.data[this.props.name] || {};
        this.graphData = graphData;
        this.hasPersistedNodes = Array.isArray(graphData.nodes) && graphData.nodes.length;
        this.state = proxy({
            nodes: this.hasPersistedNodes
                ? graphData.nodes.map(copyNode)
                : [
                      this.registry.create("start", {
                          position: { x: 120, y: 180 },
                      }),
                  ],
            connections: Array.isArray(graphData.connections)
                ? graphData.connections.map((connection) => ({ ...connection }))
                : [],
        });
        this.nextNodeId = 1;
        this.viewport = graphData.viewport || { x: 0, y: 0, scale: 1 };
        // Zooming (wheel) fires continuously; debounce so it settles into a
        // single record update once it stops instead of on every frame.
        // Panning is excluded from this debounce (see onPan/onViewportChange)
        // since it holds the pointer down for the whole gesture. execBeforeUnmount
        // flushes it if the user navigates away mid-gesture, so the latest
        // viewport is never silently dropped.
        this.debouncedUpdateRecord = useDebounced(() => this.updateRecord(), 300, {
            execBeforeUnmount: true,
        });
        useOnChange(
            () => [this.props.record.data[this.props.name]],
            () => {
                const currentGraphData = this.props.record.data[this.props.name] || {};
                if (currentGraphData === this.graphData) {
                    return;
                }
                this.graphData = currentGraphData;
                this.state.nodes = Array.isArray(currentGraphData.nodes)
                    ? currentGraphData.nodes.map(copyNode)
                    : [];
                this.state.connections = Array.isArray(currentGraphData.connections)
                    ? currentGraphData.connections.map((connection) => ({ ...connection }))
                    : [];
                this.viewport = currentGraphData.viewport || { x: 0, y: 0, scale: 1 };
            }
        );
        if (!this.hasPersistedNodes) {
            onMounted(() => this.updateRecord());
        }
    }

    get nameLabel() {
        return _t("Name");
    }

    get nameInputId() {
        return `${this.props.id}_name`;
    }

    get namePlaceholder() {
        return _t("Call flow name");
    }

    updateRecord() {
        this.graphData = {
            nodes: this.state.nodes.map(copyNode),
            connections: this.state.connections.map((connection) => ({ ...connection })),
            viewport: { ...this.viewport },
        };
        return this.props.record.update({ [this.props.name]: this.graphData });
    }

    onNodeClick({ node }) {
        if (this.props.readonly) {
            return;
        }
        if (this.registry.getNodeConfiguration(node)) {
            this.configureNode(node);
            return;
        }
        if (node.record?.resModel && node.record?.resId) {
            this.openNodeRecord(node);
            return;
        }
        this.configureNode(node);
    }

    onConnectionRejected({ validation }) {
        const messages = {
            consumer_rejected: _t("The module rejected this connection."),
            duplicate: _t("This connection already exists."),
            incompatible_ports: _t("These ports are not compatible."),
            invalid_consumer_validation: _t("The module returned an invalid validation result."),
            source_node_missing: _t("The source node no longer exists."),
            source_port_missing: _t("The source port no longer exists."),
            source_saturated: _t("The source has reached its connection limit."),
            target_node_missing: _t("The target node no longer exists."),
            target_port_missing: _t("The target port no longer exists."),
            target_saturated: _t("The target has reached its connection limit."),
        };
        this.notification.add(
            messages[validation.reason] || _t("This connection is not allowed."),
            { type: "warning" }
        );
    }

    onNodeDrop({ type, clientX, clientY, canvasRect }) {
        this.addNode(type, screenToWorld({ x: clientX, y: clientY }, canvasRect, this.viewport));
    }

    addNode(type, center) {
        const definition = this.registry.get(type);
        let nodeId;
        do {
            nodeId = `${type}-${this.nextNodeId++}`;
        } while (this.state.nodes.some((node) => node.id === nodeId));
        const node = this.registry.create(type, {
            id: nodeId,
            nodes: this.state.nodes,
            position: {
                x: center.x - definition.size.width / 2,
                y: center.y - definition.size.height / 2,
            },
        });
        if (RECORD_CONFIGS[type] || this.registry.getNodeConfiguration(node)) {
            this.configureNode(node, { removeOnCancel: true });
        } else {
            this.state.nodes = [...this.state.nodes, node];
            this.updateRecord();
        }
    }

    onNodeSelect(type) {
        const canvasRect = this.canvasRef().getBoundingClientRect();
        this.addNode(
            type,
            screenToWorld(
                {
                    x: canvasRect.left + canvasRect.width / 2,
                    y: canvasRect.top + canvasRect.height / 2,
                },
                canvasRect,
                this.viewport
            )
        );
    }

    onViewportChange(viewport) {
        this.viewport = viewport;
        // While panning, record.update() marks the field dirty, and that
        // save-state UI change was observed to break the pointer's implicit
        // grab mid-gesture (reproduced identically in Chrome and Firefox) -
        // so it must not run until the gesture actually ends (onPan below).
        // Kept for other viewport changes (e.g. wheel zoom) that aren't tied
        // to a held pointer.
        if (!this.isPanning) {
            this.debouncedUpdateRecord();
        }
    }

    onPan({ phase }) {
        if (phase === "start") {
            this.isPanning = true;
            this.debouncedUpdateRecord.cancel(false);
        } else {
            this.isPanning = false;
            this.updateRecord();
        }
    }

    getNodeComponent(node) {
        return this.registry.getNodeComponent(node);
    }

    configureNode(node, { removeOnCancel = false } = {}) {
        const cancel = () => {
            if (removeOnCancel) {
                const nodes = this.state.nodes.filter((candidate) => candidate.id !== node.id);
                if (nodes.length !== this.state.nodes.length) {
                    this.state.nodes = nodes;
                    this.updateRecord();
                }
            }
        };
        const recordConfig = RECORD_CONFIGS[node.type];
        if (recordConfig) {
            const draft = copyNode(node);
            let creating = false;
            let selected = false;
            // A node's own record (e.g. the Menu behind "Play Audio") can
            // differ from what its picker searches/creates (e.g. a Sound):
            // pickerResModel/resolveRecordId let a node type pick from one
            // model while ending up configured with a record of another.
            const pickerResModel = recordConfig.pickerResModel || recordConfig.resModel;
            const selectRecord = async (pickedId) => {
                const recordId = recordConfig.resolveRecordId
                    ? await recordConfig.resolveRecordId(this.orm, pickedId)
                    : pickedId;
                await setTerminalRecordNode(this.orm, draft, recordId);
                selected = (await this.applyNodeConfiguration(draft)) !== false;
            };
            this.dialog.add(
                SelectCreateDialog,
                {
                    context: recordConfig.context || {},
                    domain: recordConfig.domain || [],
                    multiSelect: false,
                    onCreateEdit: () => {
                        creating = true;
                        this.dialog.add(
                            FormViewDialog,
                            {
                                context: recordConfig.context || {},
                                onRecordSaved: (record) => selectRecord(record.resId),
                                resModel: pickerResModel,
                                title: recordConfig.label,
                            },
                            { onClose: () => !selected && cancel() }
                        );
                    },
                    onSelected: ([recordId]) => selectRecord(recordId),
                    resModel: pickerResModel,
                    title: recordConfig.label,
                },
                { onClose: () => !creating && !selected && cancel() }
            );
            return;
        }
        const definition = this.registry.getNodeConfiguration(node);
        if (!definition) {
            return;
        }
        this.dialog.add(FlowNodeConfigurationDialog, {
            node,
            onApply: (configuredNode) => this.applyNodeConfiguration(configuredNode),
            onCancel: cancel,
            registry: this.registry,
        });
    }

    async openNodeRecord(node) {
        const recordConfig = RECORD_CONFIGS[node.type];
        // A node's own record (e.g. the Menu behind "Play Audio") can
        // differ from what it's actually edited as (e.g. its Sound):
        // editResModel/getEditRecordId let a node type open a plain form
        // for the part of its record that's meant to be user-facing.
        const editResModel = recordConfig?.editResModel || node.record.resModel;
        const editResId = recordConfig?.getEditRecordId
            ? await recordConfig.getEditRecordId(this.orm, node.record.resId)
            : node.record.resId;
        this.dialog.add(FormViewDialog, {
            context: recordConfig?.context || {},
            onRecordSaved: async () => {
                const draft = copyNode(node);
                await setTerminalRecordNode(this.orm, draft, node.record.resId);
                await this.applyNodeConfiguration(draft);
                if (["audio_message", "ivr", "voicemail"].includes(node.type)) {
                    this.env.bus.trigger("VOIP:AUDIO-MESSAGE-UPDATED", {
                        nodeType: node.type,
                        resId: node.record.resId,
                    });
                }
                if (node.type === "queue") {
                    this.env.bus.trigger("VOIP:QUEUE-AGENTS-UPDATED", node.record.resId);
                }
            },
            resId: editResId,
            resModel: editResModel,
            title: node.record.data.display_name,
        });
    }

    async applyNodeConfiguration(node) {
        const definition = this.registry.get(node.type);
        const validation = definition.validate?.(node);
        if (validation !== undefined && validation !== true) {
            this.notification.add(validation, { type: "warning" });
            return false;
        }
        const isNewNode = !this.state.nodes.some((candidate) => candidate.id === node.id);
        this.state.nodes = isNewNode
            ? [...this.state.nodes, copyNode(node)]
            : this.state.nodes.map((candidate) =>
                  candidate.id === node.id ? copyNode(node) : candidate
              );
        const outputIds = new Set(node.outputs.map((output) => output.id));
        this.state.connections = this.state.connections.filter(
            (connection) =>
                connection.sourceNodeId !== node.id || outputIds.has(connection.sourcePortId)
        );
        await this.updateRecord();
        return true;
    }

    onNodeDrag({ node, phase }) {
        if (phase === "end") {
            this.updateNode(node);
        }
    }

    onNodeResize({ node, phase }) {
        if (phase === "end") {
            // A deliberate resize by the user always wins over whatever
            // height a node type would otherwise compute from its content.
            this.updateNode({ ...node, data: { manuallyResized: true } });
        }
    }

    updateNode(node) {
        this.state.nodes = this.state.nodes.map((candidate) =>
            candidate.id === node.id
                ? {
                      ...candidate,
                      position: { ...node.position },
                      ...(node.size ? { size: { ...node.size } } : {}),
                      ...(node.data ? { data: { ...candidate.data, ...node.data } } : {}),
                  }
                : candidate
        );
        this.updateRecord();
    }

    onConnect(connection) {
        this.state.connections = [...this.state.connections, connection];
        this.updateRecord();
        return connection;
    }

    onDisconnect({ connection }) {
        this.state.connections = this.state.connections.filter(
            (candidate) => candidate.id !== connection.id
        );
        this.updateRecord();
        return true;
    }

    onNodeDelete({ node }) {
        this.state.nodes = this.state.nodes.filter((candidate) => candidate.id !== node.id);
        this.updateRecord();
        return true;
    }
}

export const callFlowField = {
    component: CallFlowField,
    displayName: _t("Call Flow Editor"),
    supportedTypes: ["json"],
};

registry.category("fields").add("voip_call_flow_editor", callFlowField);
