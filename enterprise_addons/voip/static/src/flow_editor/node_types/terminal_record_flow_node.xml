<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="voip.TerminalRecordFlowNode">
        <header class="o_flow_editor_node_header card-header text-truncate fw-semibold" t-att-style="this.headerStyle"><i class="oi me-2" t-att-class="this.iconClass" t-att-data-icon="this.icon" aria-hidden="true"/><t t-out="this.label"/></header>
        <div class="o_flow_editor_node_body card-body overflow-hidden">
            <div class="d-flex align-items-center gap-1">
                <button t-if="['audio_message', 'ivr', 'voicemail'].includes(this.props.node.type)" class="btn btn-link btn-sm flex-shrink-0 p-0" type="button" t-att-disabled="!this.canPlayAudio" t-att-title="this.audioLabel" t-att-aria-label="this.audioLabel" t-on-click.stop="this.toggleAudio"><i class="oi" t-att-data-icon="this.state.isPlaying ? 'stop' : 'play_arrow'" aria-hidden="true"/></button>
                <div class="small text-truncate" style="min-width: 0;" t-att-class="{'text-muted': !['call_group', 'queue'].includes(this.props.node.type)}"><t t-out="this.description"/></div>
            </div>
            <ul t-if="this.props.node.type === 'call_group'" class="list-unstyled small text-muted mb-0 mt-1">
                <li t-foreach="this.userDisplayNames" t-as="userDisplayName" t-key="userDisplayName_index" class="text-truncate"><t t-out="userDisplayName"/></li>
            </ul>
            <ul t-if="this.props.node.type === 'queue'" class="o_voip_queue_node_agents list-unstyled small mb-0 mt-1">
                <li t-foreach="this.queueAgents" t-as="agent" t-key="agent.id" class="d-flex align-items-center justify-content-between gap-2 mt-1">
                    <span class="text-muted text-truncate"><t t-out="agent.displayName"/></span>
                    <span t-att-class="'badge rounded-pill flex-shrink-0 ' + agent.badgeClass"><t t-out="agent.label"/></span>
                </li>
            </ul>
        </div>
    </t>
</templates>
