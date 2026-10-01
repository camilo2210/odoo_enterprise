import {
    Component,
    onWillDestroy,
    onWillStart,
    proxy,
    t,
    useOnChange,
    useProps,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";

import { computeCallGroupNodeHeight, computeQueueNodeHeight } from "./content_height";
import { loadAudioMessageNodeData, loadIvrNodeData } from "./ivr_utils";

let activeAudio;

const AUDIO_MESSAGE_FIELDS = {
    audio_message: "menu_sound_id",
    ivr: "menu_sound_id",
    voicemail: "audio_message_id",
};

export const RECORD_CONFIGS = {
    audio_message: {
        context: { voip_call_flow_audio_creation: true },
        // Picks/creates, and later re-edits, a Sound: the Menu that
        // actually backs this node's outputs is an implementation detail,
        // built by resolveRecordId and bypassed by editResModel/
        // getEditRecordId so the user only ever sees a sound, never a menu.
        domain: [["data", "!=", false]],
        editResModel: "voip.sound",
        async getEditRecordId(orm, ivrId) {
            const [ivr] = await orm.read("voip.ivr", [ivrId], ["menu_sound_id"]);
            return ivr.menu_sound_id[0];
        },
        icon: "volume_up",
        label: _t("Play Audio"),
        pickerResModel: "voip.sound",
        resModel: "voip.ivr",
        async resolveRecordId(orm, soundId) {
            return orm.call("voip.ivr", "get_or_create_audio_message_wrapper", [soundId]);
        },
    },
    call_group: {
        context: { voip_call_flow_node_configuration: true },
        domain: [["callflow_id", "=", false]],
        icon: "group",
        icon_class: "oi-filled",
        label: _t("Call a Group"),
        resModel: "voip.call.group",
    },
    contact: {
        domain: [["phone", "!=", false]],
        icon: "contact_mail",
        icon_class: "oi-filled",
        label: _t("Call a Contact"),
        resModel: "res.partner",
    },
    extension: {
        icon: "phone",
        icon_class: "oi-filled",
        label: _t("Redirect to an Extension"),
        resModel: "voip.extension",
    },
    ivr: {
        context: {
            voip_call_flow_audio_creation: true,
            voip_call_flow_node_configuration: true,
        },
        domain: [["callflow_id", "=", false]],
        icon: "format_list_numbered",
        label: _t("Open a Menu"),
        resModel: "voip.ivr",
    },
    queue: {
        context: { voip_call_flow_node_configuration: true },
        domain: [["callflow_id", "=", false]],
        icon: "headphones",
        label: _t("Send to a Queue"),
        resModel: "voip.queue",
    },
    time_condition: {
        context: { voip_call_flow_node_configuration: true },
        domain: [["callflow_id", "=", false]],
        icon: "schedule",
        label: _t("Time Condition"),
        resModel: "voip.time.condition",
    },
    user: {
        context: { voip_call_flow_node_configuration: true },
        domain: [
            ["active", "=", true],
            ["share", "=", false],
        ],
        icon: "person",
        icon_class: "oi-filled",
        label: _t("Call a User"),
        resModel: "res.users",
    },
    voicemail: {
        icon: "inbox",
        label: _t("Send to Voicemail"),
        resModel: "voip.voicemail",
    },
};

// Mirrors the badge colors/labels of the "status" field on the Queue
// form's Agents tab (voip_queue_views.xml) so an agent's pill reads the
// same whether it's viewed there or on this Call Flow queue node.
const QUEUE_AGENT_STATUSES = {
    available: { badgeClass: "text-bg-success", label: _t("Available") },
    in_call: { badgeClass: "text-bg-success", label: _t("In Call") },
    logged_out: { badgeClass: "text-bg-danger", label: _t("Disconnected") },
    paused: { badgeClass: "text-bg-danger", label: _t("On Pause") },
    unavailable: { badgeClass: "text-bg-danger", label: _t("No Device Detected") },
    unknown: { badgeClass: "text-bg-secondary", label: _t("Unknown") },
};

export class TerminalRecordFlowNode extends Component {
    static template = "voip.TerminalRecordFlowNode";

    props = useProps({
        node: t.object(),
        readonly: t.boolean(),
    });

    setup() {
        this.orm = useService("orm");
        this.state = proxy({
            audioMessage: null,
            isPlaying: false,
            queueAgents: [],
            userDisplayNames: [],
        });
        this.audio = null;
        this.audioMessageRequestId = 0;
        this.audioRecordKey = null;
        this.callGroupId = null;
        this.queueAgentsRequestId = 0;
        this.queueId = null;
        onWillStart(() => this.loadNodeData(this.props.node));
        useOnChange(
            () => [
                this.props.node.type,
                this.props.node.record?.resId,
                this.props.node.record?.data?.user_display_names,
            ],
            () => {
                // The sound being played belongs to the record we are leaving:
                // once it is gone the play button is disabled, so a sound left
                // running here could no longer be stopped by the user.
                this.audio?.pause();
                this.loadNodeData(this.props.node);
            },
            { initialRun: false }
        );
        useBus(this.env.bus, "VOIP:QUEUE-AGENTS-UPDATED", ({ detail: queueId }) => {
            if (this.props.node.type === "queue" && this.props.node.record?.resId === queueId) {
                this.queueId = null;
                this.loadQueueAgents(this.props.node);
            }
        });
        useBus(this.env.bus, "VOIP:AUDIO-MESSAGE-UPDATED", ({ detail: { nodeType, resId } }) => {
            if (this.props.node.type === nodeType && this.props.node.record?.resId === resId) {
                this.audioRecordKey = null;
                this.loadAudioMessage(this.props.node);
            }
        });
        onWillDestroy(() => this.audio?.pause());
    }

    /**
     * @param {import("@voip/core/flow_editor/flow_types").FlowNode} node
     */
    loadNodeData(node) {
        return Promise.all([
            this.loadAudioMessage(node),
            this.loadQueueAgents(node),
            this.loadUserDisplayNames(node),
        ]);
    }

    get description() {
        return this.props.node.record?.data?.display_name || _t("No record selected");
    }

    get audioLabel() {
        return this.state.isPlaying ? _t("Stop") : _t("Play");
    }

    get canPlayAudio() {
        return Boolean(this.state.audioMessage);
    }

    get headerStyle() {
        return `height: ${this.props.node.headerHeight ?? 40}px;`;
    }

    get icon() {
        return RECORD_CONFIGS[this.props.node.type].icon;
    }

    get iconClass() {
        return RECORD_CONFIGS[this.props.node.type].icon_class;
    }

    get label() {
        return RECORD_CONFIGS[this.props.node.type].label;
    }

    get queueAgents() {
        return this.state.queueAgents.map((agent) => ({
            ...agent,
            ...QUEUE_AGENT_STATUSES[agent.status],
            displayName: agent.user_id[1],
        }));
    }

    get userDisplayNames() {
        return this.state.userDisplayNames;
    }

    async loadAudioMessage(node) {
        const relationField = AUDIO_MESSAGE_FIELDS[node.type];
        const recordKey = node.record?.resId ? `${node.type}:${node.record.resId}` : null;
        if (recordKey === this.audioRecordKey) {
            return;
        }
        const requestId = ++this.audioMessageRequestId;
        this.audioRecordKey = recordKey;
        if (relationField === undefined || !node.record?.resId) {
            this.state.audioMessage = null;
            return;
        }
        let audioMessageId = node.record.resId;
        if (relationField) {
            const [record] = await this.orm.read(
                node.record.resModel,
                [node.record.resId],
                [relationField]
            );
            audioMessageId = record[relationField]?.[0];
        }
        if (!audioMessageId) {
            if (requestId === this.audioMessageRequestId) {
                this.state.audioMessage = null;
            }
            return;
        }
        const [audioMessage] = await this.orm.read(
            "voip.sound",
            [audioMessageId],
            ["data_version"]
        );
        if (requestId === this.audioMessageRequestId) {
            this.state.audioMessage = audioMessage;
        }
    }

    async loadQueueAgents(node) {
        const queueId = node.type === "queue" ? node.record?.resId || null : null;
        if (queueId === this.queueId) {
            return;
        }
        const requestId = ++this.queueAgentsRequestId;
        this.queueId = queueId;
        if (!queueId) {
            this.state.queueAgents = [];
            return;
        }
        const agents = await this.orm.searchRead(
            "voip.queue.agent",
            [["queue_id", "=", queueId]],
            ["status", "user_id"],
            { order: "sequence, id" }
        );
        if (requestId === this.queueAgentsRequestId) {
            this.state.queueAgents = agents;
        }
    }

    async loadUserDisplayNames(node) {
        const callGroupId = node.type === "call_group" ? node.record?.resId || null : null;
        if (Array.isArray(node.record?.data?.user_display_names)) {
            this.callGroupId = callGroupId;
            this.state.userDisplayNames = node.record.data.user_display_names;
            return;
        }
        if (callGroupId === this.callGroupId) {
            return;
        }
        this.callGroupId = callGroupId;
        if (!callGroupId) {
            this.state.userDisplayNames = [];
            return;
        }
        const [callGroup] = await this.orm.read(
            "voip.call.group",
            [callGroupId],
            ["user_display_names"]
        );
        if (callGroupId === this.callGroupId) {
            this.state.userDisplayNames = callGroup?.user_display_names || [];
        }
    }

    async toggleAudio() {
        if (!this.canPlayAudio) {
            return;
        }
        if (this.state.isPlaying) {
            this.audio.pause();
            this.audio.currentTime = 0;
            return;
        }
        activeAudio?.pause();
        const { data_version: dataVersion, id } = this.state.audioMessage;
        this.audio = new Audio(`/voip/audio/message/${id}?v=${dataVersion || 0}`);
        this.audio.addEventListener("ended", () => (this.state.isPlaying = false));
        this.audio.addEventListener("pause", () => (this.state.isPlaying = false));
        try {
            await this.audio.play();
            activeAudio = this.audio;
            this.state.isPlaying = true;
        } catch {
            this.state.isPlaying = false;
        }
    }
}

export async function setTerminalRecordNode(orm, draft, recordId) {
    const config = RECORD_CONFIGS[draft.type];
    let [recordData] = await orm.read(config.resModel, [recordId], ["display_name"]);
    // The user's own resize takes precedence over the height a node type
    // would otherwise compute from its record's content.
    const manuallyResized = Boolean(draft.data?.manuallyResized);
    if (draft.type === "ivr") {
        const ivrNodeData = await loadIvrNodeData(orm, recordId);
        recordData = ivrNodeData.recordData;
        draft.outputs = ivrNodeData.outputs;
        if (!manuallyResized) {
            draft.size.height = ivrNodeData.height;
        }
    } else if (draft.type === "audio_message") {
        const audioMessageNodeData = await loadAudioMessageNodeData(orm, recordId);
        recordData = audioMessageNodeData.recordData;
        draft.outputs = audioMessageNodeData.outputs;
    } else if (draft.type === "queue") {
        if (!manuallyResized) {
            const agentCount = await orm.searchCount("voip.queue.agent", [
                ["queue_id", "=", recordId],
            ]);
            draft.size.height = computeQueueNodeHeight(agentCount);
        }
    } else if (draft.type === "call_group") {
        const [callGroup] = await orm.read(
            "voip.call.group",
            [recordId],
            ["display_name", "user_display_names"]
        );
        recordData = callGroup;
        if (!manuallyResized) {
            draft.size.height = computeCallGroupNodeHeight(
                callGroup?.user_display_names.length || 0
            );
        }
    }
    draft.record = {
        resModel: config.resModel,
        resId: recordId,
        data: recordData,
    };
    draft.data.label = config.label;
}
