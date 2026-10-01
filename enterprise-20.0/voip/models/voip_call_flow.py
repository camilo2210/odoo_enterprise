from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .pbx_service import PBX_DESTINATION_MODELS


CALL_FLOW_OUTPUT_NODE_MODELS = {
    "audio_message": "voip.ivr",
    "call_group": "voip.call.group",
    "ivr": "voip.ivr",
    "queue": "voip.queue",
    "time_condition": "voip.time.condition",
}
CALL_FLOW_OUTPUT_FIELDS = {
    "voip.call.group": ("no_answer_destination_ref",),
    "voip.ivr": (
        "abort_destination_ref",
        "invalid_destination_ref",
        "timeout_destination_ref",
    ),
    "voip.queue": (
        "no_answer_destination_ref",
        "busy_destination_ref",
    ),
    "voip.time.condition": ("open_destination_ref", "closed_destination_ref"),
}
CALL_FLOW_RECORD_NODE_MODELS = {
    # "Play Audio" is a Menu (voip.ivr) with one option per key -- all
    # routed to the same "Skip" output -- so pressing any key or letting it
    # play out are its only two outputs. Wrapping a Menu is the only way to
    # give a bare sound message an output at all: the PBX has no "play
    # sound then continue" primitive of its own.
    "audio_message": "voip.ivr",
    "call_group": "voip.call.group",
    "contact": "res.partner",
    "extension": "voip.extension",
    "ivr": "voip.ivr",
    "queue": "voip.queue",
    "time_condition": "voip.time.condition",
    "user": "res.users",
    "voicemail": "voip.voicemail",
}
GRAPH_LAYOUT_NODE_KEYS = frozenset({"position", "size"})


class VoipCallFlow(models.Model):
    _name = "voip.call.flow"
    _inherit = "voip.pbx.destination.mixin"
    _description = "VoIP Call Flow"
    _order = "name, id"

    @api.model
    def _default_graph_data(self):
        return {
            "nodes": [{
                "id": "start",
                "type": "start",
                "position": {"x": 120, "y": 180},
                "shape": "circle",
                "size": {"width": 64, "height": 64},
                "outputs": [{
                    "id": "next",
                    "direction": "output",
                    "provides": "flow",
                    "maxConnections": 1,
                }],
                "data": {"label": self.env._("Start")},
                "deletable": False,
            }],
            "connections": [],
        }

    name = fields.Char(default=lambda self: self.env._("Call flow"), required=True)
    graph_data = fields.Json(default=_default_graph_data)
    node_count = fields.Integer(compute="_compute_node_count", store=True)
    active = fields.Boolean(default=True)

    @api.depends("graph_data")
    def _compute_node_count(self):
        for call_flow in self:
            graph_data = call_flow.graph_data or {}
            nodes = graph_data.get("nodes")
            call_flow.node_count = len(nodes) if isinstance(nodes, list) else 0

    @api.model_create_multi
    def create(self, vals_list):
        default_name = self.env._("Call flow")
        uses_default_name = [
            not vals.get("name") or vals["name"] == default_name
            for vals in vals_list
        ]
        for vals, use_default_name in zip(vals_list, uses_default_name, strict=True):
            if use_default_name:
                vals["name"] = default_name
        call_flows = super().create(vals_list)
        for call_flow, use_default_name in zip(call_flows, uses_default_name, strict=True):
            if use_default_name:
                call_flow.name = self.env._("Call flow %(id)s", id=call_flow.id)
        call_flows._validate_graphs()
        active_call_flows = call_flows.filtered("active")
        active_call_flows._ensure_graph_users_exist_in_pbx()
        active_call_flows._ensure_graph_sounds_exist_in_pbx()
        call_flows._sync_graph_memberships()
        active_call_flows._sync_graph_call_groups()
        active_call_flows._sync_graph_ivrs()
        active_call_flows._sync_graph_queues()
        active_call_flows._sync_graph_time_conditions()
        return call_flows

    def write(self, vals):
        previous_signatures = (
            {call_flow.id: call_flow._get_graph_pbx_signature() for call_flow in self}
            if "graph_data" in vals
            else {}
        )
        result = super().write(vals)
        if {"active", "graph_data"} & vals.keys():
            self._validate_graphs()
            pbx_relevant_call_flows = self.filtered(
                lambda call_flow: "active" in vals
                or call_flow._get_graph_pbx_signature() != previous_signatures.get(call_flow.id)
            )
            active_call_flows = pbx_relevant_call_flows.filtered("active")
            active_call_flows._ensure_graph_users_exist_in_pbx()
            active_call_flows._ensure_graph_sounds_exist_in_pbx()
            pbx_relevant_call_flows._sync_graph_memberships()
            pbx_relevant_call_flows._sync_graph_routes()
        return result

    def _get_graph_pbx_signature(self):
        """Project graph_data onto what PBX sync cares about, ignoring canvas layout.

        Moving or resizing a node on the canvas must not trigger a PBX resync: it
        changes nothing about routing, so `position`/`size` are stripped before
        comparing the graph to what was last synced.
        """
        self.ensure_one()
        graph_data = self.graph_data or {}
        nodes = graph_data.get("nodes")
        if not isinstance(nodes, list):
            return graph_data
        nodes_by_id = {
            node.get("id"): {
                key: value for key, value in node.items() if key not in GRAPH_LAYOUT_NODE_KEYS
            }
            for node in nodes
            if isinstance(node, dict)
        }
        return nodes_by_id, graph_data.get("connections")

    def _sync_graph_routes(self):
        active_call_flows = self.filtered("active")
        active_call_flows._sync_graph_call_groups()
        active_call_flows._sync_graph_ivrs()
        active_call_flows._sync_graph_queues()
        active_call_flows._sync_graph_time_conditions()
        self._sync_pbx_references()

    def _validate_graphs(self):
        """Validate complete graphs before triggering any external PBX effect."""
        owners_by_record = {}
        for call_flow in self:
            records_by_model = call_flow._validate_graph_data()
            if not call_flow.active:
                continue
            for records in records_by_model.values():
                for record in records:
                    record_key = (record._name, record.id)
                    if record_key in owners_by_record:
                        raise ValidationError(self.env._(
                            "%(record_name)s cannot be used more than once in Call Flows.",
                            record_name=record.display_name,
                        ))
                    owners_by_record[record_key] = call_flow
                    if record.callflow_id and record.callflow_id != call_flow:
                        raise ValidationError(self.env._(
                            "%(record_name)s is already used in the Call Flow %(call_flow_name)s.",
                            record_name=record.display_name,
                            call_flow_name=record.callflow_id.display_name,
                        ))

    def _validate_graph_data(self):
        """Validate graph structure, record references and Time Condition placement."""
        self.ensure_one()
        graph_data = self.graph_data
        if not isinstance(graph_data, dict):
            raise ValidationError(self.env._("The Call Flow graph must be an object."))
        nodes = graph_data.get("nodes")
        connections = graph_data.get("connections")
        if not isinstance(nodes, list) or not isinstance(connections, list):
            raise ValidationError(
                self.env._("The Call Flow graph must contain nodes and connections.")
            )

        nodes_by_id = {}
        records_by_model = {
            model_name: self.env[model_name]
            for model_name in CALL_FLOW_OUTPUT_NODE_MODELS.values()
        }
        for node in nodes:
            if (
                not isinstance(node, dict)
                or not isinstance(node.get("id"), (int, str))
                or isinstance(node.get("id"), bool)
            ):
                raise ValidationError(self.env._("Every Call Flow node must have a valid ID."))
            node_id = node["id"]
            if node_id in nodes_by_id:
                raise ValidationError(self.env._("Call Flow node IDs must be unique."))
            nodes_by_id[node_id] = node
            node_type = node.get("type")
            if node_type not in (*CALL_FLOW_RECORD_NODE_MODELS, "hangup", "outcall", "start"):
                raise ValidationError(self.env._("The Call Flow contains an unsupported node."))
            if not isinstance(node.get("outputs"), list):
                raise ValidationError(self.env._("Every Call Flow node must define its outputs."))
            output_ids = [
                output.get("id")
                for output in node["outputs"]
                if isinstance(output, dict)
                and isinstance(output.get("id"), (int, str))
                and output.get("direction") == "output"
            ]
            if len(output_ids) != len(node["outputs"]) or len(output_ids) != len(set(output_ids)):
                raise ValidationError(self.env._("A Call Flow node has invalid output ports."))

            expected_model = CALL_FLOW_RECORD_NODE_MODELS.get(node_type)
            if expected_model:
                record_data = node.get("record")
                if (
                    not isinstance(record_data, dict)
                    or record_data.get("resModel") != expected_model
                    or not isinstance(record_data.get("resId"), int)
                ):
                    raise ValidationError(self.env._(
                        "The %(node_type)s node has an invalid destination.",
                        node_type=node_type,
                    ))
                record = self.env[expected_model].browse(record_data["resId"]).exists()
                if not record:
                    raise ValidationError(
                        self.env._("A destination used by the Call Flow no longer exists.")
                    )
                if expected_model in records_by_model:
                    if record in records_by_model[expected_model]:
                        raise ValidationError(self.env._(
                            "%(record_name)s cannot be used more than once in the same Call Flow.",
                            record_name=record.display_name,
                        ))
                    records_by_model[expected_model] |= record

        start_nodes = [node for node in nodes if node["type"] == "start"]
        if len(start_nodes) != 1:
            raise ValidationError(
                self.env._("The Call Flow must contain exactly one Start node.")
            )
        if start_nodes[0].get("input") or [
            output["id"] for output in start_nodes[0]["outputs"]
        ] != ["next"]:
            raise ValidationError(
                self.env._("The Start node must have exactly one output and no input.")
            )

        seen_connections = set()
        connection_counts = {}
        for connection in connections:
            if not isinstance(connection, dict):
                raise ValidationError(self.env._("The Call Flow contains an invalid connection."))
            source = nodes_by_id.get(connection.get("sourceNodeId"))
            target = nodes_by_id.get(connection.get("targetNodeId"))
            if not source or not target:
                raise ValidationError(self.env._("The Call Flow contains an invalid connection."))
            source_port_id = connection.get("sourcePortId")
            target_port_id = connection.get("targetPortId")
            source_port = next(
                (output for output in source["outputs"] if output["id"] == source_port_id),
                None,
            )
            target_port = target.get("input")
            if not isinstance(target_port, dict) or target_port.get("direction") != "input":
                target_port = None
            if not source_port or not target_port or target_port.get("id") != target_port_id:
                raise ValidationError(self.env._("A Call Flow connection uses an invalid port."))
            if (
                target_port.get("accepts") is not None
                and source_port.get("provides") not in target_port["accepts"]
            ):
                raise ValidationError(
                    self.env._("A Call Flow connection uses incompatible ports.")
                )
            connection_key = (source["id"], source_port_id, target["id"], target_port_id)
            if connection_key in seen_connections:
                raise ValidationError(self.env._("The Call Flow contains a duplicate connection."))
            seen_connections.add(connection_key)
            for port_key, port in (
                (("source", source["id"], source_port_id), source_port),
                (("target", target["id"], target_port_id), target_port),
            ):
                connection_counts[port_key] = connection_counts.get(port_key, 0) + 1
                if (
                    port.get("maxConnections") is not None
                    and connection_counts[port_key] > port["maxConnections"]
                ):
                    raise ValidationError(
                        self.env._("A Call Flow connection uses a saturated port.")
                    )

        time_condition_nodes = [
            node for node in nodes
            if isinstance(node, dict) and node.get("type") == "time_condition"
        ]
        start_target = self._get_graph_output_nodes(
            start_nodes[0], ("next",), nodes_by_id, connections
        )["next"]
        connected_node_ids = {connection["targetNodeId"] for connection in connections}
        claimed_owner_node_ids = set()
        for node in time_condition_nodes:
            if [output["id"] for output in node["outputs"]] != ["open", "closed"]:
                raise ValidationError(self.env._(
                    "A Time Condition node must have one Open and one Closed output."
                ))
            if node == start_target:
                continue
            open_target = self._get_graph_output_nodes(
                node, ("open",), nodes_by_id, connections
            )["open"]
            if not open_target or open_target.get("type") not in ("call_group", "queue"):
                if node["id"] not in connected_node_ids:
                    continue
                raise ValidationError(self.env._(
                    "A Time Condition outside Start must have its Open output connected to a "
                    "Call Group or Queue."
                ))
            if open_target["id"] in claimed_owner_node_ids:
                raise ValidationError(self.env._(
                    "A Call Group or Queue cannot use more than one Time Condition."
                ))
            claimed_owner_node_ids.add(open_target["id"])
        return records_by_model

    def _sync_graph_memberships(self):
        """Assign output-bearing PBX records exclusively to their Call Flow."""
        records_by_call_flow = {}
        owners_by_record = {}
        for call_flow in self:
            records_by_call_flow[call_flow] = call_flow._get_graph_output_records()
            for records in records_by_call_flow[call_flow].values():
                for record in records:
                    record_key = (record._name, record.id)
                    if record_key in owners_by_record:
                        raise ValidationError(self.env._(
                            "%(record_name)s cannot be used more than once in Call Flows.",
                            record_name=record.display_name,
                        ))
                    owners_by_record[record_key] = call_flow
                    if record.callflow_id and record.callflow_id != call_flow:
                        raise ValidationError(self.env._(
                            "%(record_name)s is already used in the Call Flow %(call_flow_name)s.",
                            record_name=record.display_name,
                            call_flow_name=record.callflow_id.display_name,
                        ))

        sync_context = {"voip_call_flow_sync": True}
        for model_name in CALL_FLOW_OUTPUT_NODE_MODELS.values():
            assigned_records = self.env[model_name].search([
                ("callflow_id", "in", self.ids),
            ])
            desired_records = self.env[model_name]
            for call_flow, records_by_model in records_by_call_flow.items():
                records = records_by_model[model_name]
                desired_records |= records
                records.filtered(
                    lambda record: record.callflow_id != call_flow
                ).with_context(**sync_context).callflow_id = call_flow
            released_records = assigned_records - desired_records
            self._release_output_owning_records(
                released_records, CALL_FLOW_OUTPUT_FIELDS[model_name]
            )

    def _release_output_owning_records(self, records, output_fields):
        """Clear Call Flow membership and PBX destinations on released records.

        IVRs need their options' destinations cleared too and an explicit
        PBX resync, unlike Call Group/Queue whose own write() already
        triggers it.
        """
        if not records:
            return
        sync_context = {"voip_call_flow_sync": True}
        if records._name == "voip.ivr":
            records.with_context(
                **sync_context, voip_skip_pbx_sync=True
            ).write({
                "callflow_id": False,
                **dict.fromkeys(output_fields, False),
            })
            records.option_ids.with_context(
                **sync_context, voip_skip_pbx_sync=True
            ).write({"destination_ref": False})
            records._sync_pbx()
        elif records._name == "voip.time.condition":
            records._release_from_call_flow()
        else:
            records.with_context(**sync_context).write({
                "callflow_id": False,
                **dict.fromkeys(output_fields, False),
            })

    @api.ondelete(at_uninstall=False)
    def _release_graph_memberships(self):
        references = self._get_pbx_reference_owners()
        blocking_references = [
            record
            for model_name, records in references.items()
            if model_name != "voip.did.number"
            for record in records
        ]
        if blocking_references:
            raise ValidationError(self.env._(
                "This Call Flow is still used by:\n%(references)s\n"
                "Reassign those destinations before deleting it.",
                references="\n".join(
                    f"- {record._description}: {record.display_name}"
                    for record in blocking_references
                ),
            ))
        for model_name, output_fields in CALL_FLOW_OUTPUT_FIELDS.items():
            records = self.env[model_name].search([("callflow_id", "in", self.ids)])
            self._release_output_owning_records(records, output_fields)

    def _get_graph_output_records(self):
        """Return records whose PBX output branches are owned by this graph."""
        self.ensure_one()
        records_by_model = {
            model_name: self.env[model_name]
            for model_name in CALL_FLOW_OUTPUT_NODE_MODELS.values()
        }
        if not self.active:
            return records_by_model
        graph_data = self.graph_data or {}
        nodes = graph_data.get("nodes")
        if not isinstance(nodes, list):
            return records_by_model
        record_keys = set()
        for node in nodes:
            if (
                not isinstance(node, dict)
                or node.get("type") not in CALL_FLOW_OUTPUT_NODE_MODELS
            ):
                continue
            model_name = CALL_FLOW_OUTPUT_NODE_MODELS[node["type"]]
            record = node.get("record")
            if (
                not isinstance(record, dict)
                or record.get("resModel") != model_name
                or not isinstance(record.get("resId"), int)
            ):
                raise ValidationError(self.env._(
                    "The %(node_type)s node has an invalid destination.",
                    node_type=node["type"],
                ))
            destination = self.env[model_name].browse(record["resId"]).exists()
            if not destination:
                raise ValidationError(self.env._(
                    "A destination used by the Call Flow no longer exists."
                ))
            record_key = (model_name, destination.id)
            if record_key in record_keys:
                raise ValidationError(self.env._(
                    "%(record_name)s cannot be used more than once in the same Call Flow.",
                    record_name=destination.display_name,
                ))
            record_keys.add(record_key)
            records_by_model[model_name] |= destination
        return records_by_model

    @staticmethod
    def _reference_str(value):
        """Serialize a Reference field's current value like
        _get_graph_output_destinations resolves a target node, so the two
        can be compared before writing/syncing anything.
        """
        return f"{value._name},{value.id}" if value else False

    def _sync_graph_call_groups(self):
        """Store Call Group output branches on their global fallback fields."""
        for call_flow in self:
            graph_data = call_flow.graph_data or {}
            nodes = graph_data.get("nodes") or []
            connections = graph_data.get("connections") or []
            nodes_by_id = {
                node.get("id"): node
                for node in nodes
                if isinstance(node, dict) and node.get("id") is not None
            }
            for node in nodes:
                if not isinstance(node, dict) or node.get("type") != "call_group":
                    continue
                call_group = call_flow._get_route_destination(node)
                destinations = call_flow._get_graph_output_destinations(
                    node, ("no_answer",), nodes_by_id, connections
                )
                if self._reference_str(call_group.no_answer_destination_ref) == destinations["no_answer"]:
                    continue
                call_group.with_context(voip_call_flow_sync=True).write({
                    "no_answer_destination_ref": destinations["no_answer"],
                })

    def _sync_graph_queues(self):
        """Store Queue output branches on their global fallback fields."""
        for call_flow in self:
            graph_data = call_flow.graph_data or {}
            nodes = graph_data.get("nodes") or []
            connections = graph_data.get("connections") or []
            nodes_by_id = {
                node.get("id"): node
                for node in nodes
                if isinstance(node, dict) and node.get("id") is not None
            }
            for node in nodes:
                if not isinstance(node, dict) or node.get("type") != "queue":
                    continue
                queue = call_flow._get_route_destination(node)
                destinations = call_flow._get_graph_output_destinations(
                    node, ("no_answer", "busy"), nodes_by_id, connections
                )
                if (
                    self._reference_str(queue.no_answer_destination_ref) == destinations["no_answer"]
                    and self._reference_str(queue.busy_destination_ref) == destinations["busy"]
                ):
                    continue
                queue.with_context(voip_call_flow_sync=True).write({
                    "no_answer_destination_ref": destinations["no_answer"],
                    "busy_destination_ref": destinations["busy"],
                })

    def _sync_graph_time_conditions(self):
        """Store both Time Condition branches and synchronize them with Wazo."""
        for call_flow in self:
            graph_data = call_flow.graph_data or {}
            nodes = graph_data.get("nodes") or []
            connections = graph_data.get("connections") or []
            nodes_by_id = {
                node.get("id"): node
                for node in nodes
                if isinstance(node, dict) and node.get("id") is not None
            }
            first_node = call_flow._get_first_node()
            for node in nodes:
                if not isinstance(node, dict) or node.get("type") != "time_condition":
                    continue
                # Not _get_route_destination: voip.time.condition is a graph
                # node, not a dialable PBX destination (it isn't in
                # PBX_DESTINATION_MODELS), unlike the call_group/queue/ivr
                # nodes that method is normally used for.
                time_condition = call_flow.env["voip.time.condition"].browse(
                    node["record"]["resId"]
                )
                open_target = call_flow._get_graph_output_nodes(
                    node, ("open",), nodes_by_id, connections
                )["open"]
                owner = (
                    call_flow._get_route_destination(open_target)
                    if node != first_node
                    and open_target
                    and open_target.get("type") in ("call_group", "queue")
                    else False
                )
                destinations = call_flow._get_graph_output_destinations(
                    node, ("open", "closed"), nodes_by_id, connections
                )
                owner_values = {
                    "call_group_id": (
                        owner.id if owner and owner._name == "voip.call.group" else False
                    ),
                    "queue_id": owner.id if owner and owner._name == "voip.queue" else False,
                }
                previous_call_group = time_condition.call_group_id
                previous_queue = time_condition.queue_id
                if any(
                    self._reference_str(time_condition[field_name]) != destinations[output_id]
                    for field_name, output_id in (
                        ("open_destination_ref", "open"),
                        ("closed_destination_ref", "closed"),
                    )
                ) or any(
                    time_condition[field_name].id != owner_id
                    for field_name, owner_id in owner_values.items()
                ):
                    time_condition.with_context(voip_call_flow_sync=True).write({
                        "open_destination_ref": destinations["open"],
                        "closed_destination_ref": destinations["closed"],
                        **owner_values,
                    })
                if previous_call_group and previous_call_group != time_condition.call_group_id:
                    call_flow._sync_time_condition_owner_schedule(previous_call_group, None)
                if previous_queue and previous_queue != time_condition.queue_id:
                    call_flow._sync_time_condition_owner_schedule(previous_queue, None)
                time_condition._sync_pbx()

    def _sync_time_condition_owner_schedule(self, owner, schedule_id):
        service = self.env["voip.pbx.service"]
        if owner._name == "voip.call.group" and owner.pbx_group_uuid:
            service._sync_group_schedule(
                group_uuid=owner.pbx_group_uuid,
                schedule_id=schedule_id,
            )
        elif owner._name == "voip.queue" and owner.pbx_queue_id:
            service._sync_queue_schedule(
                queue_id=owner.pbx_queue_id,
                schedule_id=schedule_id,
            )

    def _sync_graph_ivrs(self):
        """Store IVR graph branches and synchronize them with Wazo."""
        for call_flow in self:
            graph_data = call_flow.graph_data or {}
            nodes = graph_data.get("nodes") or []
            connections = graph_data.get("connections") or []
            nodes_by_id = {
                node.get("id"): node
                for node in nodes
                if isinstance(node, dict) and node.get("id") is not None
            }
            for node in nodes:
                if not isinstance(node, dict) or node.get("type") not in ("ivr", "audio_message"):
                    continue
                ivr = call_flow._get_route_destination(node)
                # A "Play Audio" node shows one "Skip" output, but every key
                # the caller could press must trigger it -- there is no
                # invalid input to report -- so all of its options resolve
                # to that single port instead of one port each.
                if ivr.is_audio_message:
                    output_ids = ("skip", "timeout")
                else:
                    output_ids = tuple(
                        [f"option-{option.id}" for option in ivr.option_ids]
                        + ["invalid", "timeout", "abort"]
                    )
                destinations = call_flow._get_graph_output_destinations(
                    node, output_ids, nodes_by_id, connections
                )
                if ivr.is_audio_message:
                    option_destinations = dict.fromkeys(
                        ivr.option_ids.ids, destinations["skip"]
                    )
                    invalid_destination = None
                    abort_destination = None
                else:
                    option_destinations = {
                        option.id: destinations[f"option-{option.id}"]
                        for option in ivr.option_ids
                    }
                    invalid_destination = destinations["invalid"]
                    abort_destination = destinations["abort"]
                # A "Play Audio" node's wait must track its sound, so a
                # re-recorded or regenerated message is never cut short or
                # left with dead air -- unlike a real Menu's timeout, which
                # is a deliberate choice left alone.
                extra_vals = {}
                if ivr.is_audio_message:
                    expected_timeout = max(1, round(ivr.menu_sound_id._get_duration_seconds()))
                    if ivr.timeout != expected_timeout:
                        extra_vals["timeout"] = expected_timeout
                changed = bool(extra_vals) or (
                    self._reference_str(ivr.invalid_destination_ref) != invalid_destination
                    or self._reference_str(ivr.timeout_destination_ref) != destinations["timeout"]
                    or self._reference_str(ivr.abort_destination_ref) != abort_destination
                    or any(
                        self._reference_str(option.destination_ref)
                        != option_destinations[option.id]
                        for option in ivr.option_ids
                    )
                )
                if not changed:
                    continue
                sync_context = {
                    "voip_call_flow_sync": True,
                    "voip_skip_pbx_sync": True,
                }
                ivr.with_context(**sync_context).write({
                    "invalid_destination_ref": invalid_destination,
                    "timeout_destination_ref": destinations["timeout"],
                    "abort_destination_ref": abort_destination,
                    **extra_vals,
                })
                for option in ivr.option_ids:
                    option.with_context(**sync_context).destination_ref = option_destinations[
                        option.id
                    ]
                ivr._sync_pbx()

    def _get_graph_output_destinations(
        self, node, output_ids, nodes_by_id, connections
    ):
        """Resolve a graph node's optional output branches as Reference values."""
        target_nodes = self._get_graph_output_nodes(
            node, output_ids, nodes_by_id, connections
        )
        destinations = {}
        for output_id, target_node in target_nodes.items():
            if target_node and target_node.get("type") == "time_condition":
                target_node = self._get_graph_output_nodes(
                    target_node, ("open",), nodes_by_id, connections
                )["open"]
            if (
                not target_node
                or target_node.get("type") in ("hangup", "outcall")
            ):
                destinations[output_id] = False
                continue
            destination = self._get_route_destination(target_node)
            destinations[output_id] = f"{destination._name},{destination.id}"
        return destinations

    def _get_graph_output_nodes(self, node, output_ids, nodes_by_id, connections):
        """Return the optional target node connected to each requested output."""
        self.ensure_one()
        target_nodes = {}
        for output_id in output_ids:
            output_connections = [
                connection
                for connection in connections
                if (
                    isinstance(connection, dict)
                    and connection.get("sourceNodeId") == node.get("id")
                    and connection.get("sourcePortId") == output_id
                )
            ]
            if len(output_connections) > 1:
                raise ValidationError(self.env._(
                    "A node output can only be connected to one node."
                ))
            target_node = (
                nodes_by_id.get(output_connections[0].get("targetNodeId"))
                if output_connections
                else None
            )
            if output_connections and not target_node:
                raise ValidationError(self.env._(
                    "A node output is connected to an invalid node."
                ))
            target_nodes[output_id] = target_node
        return target_nodes

    def _get_record_output_pbx_destinations(self, record, output_ids, recovery=False):
        """Resolve a Call Flow member's output branches as PBX payloads."""
        self.ensure_one()
        graph_data = self.graph_data or {}
        nodes = graph_data.get("nodes") or []
        connections = graph_data.get("connections") or []
        member_nodes = [
            node
            for node in nodes
            if (
                isinstance(node, dict)
                and node.get("record", {}).get("resModel") == record._name
                and node["record"].get("resId") == record.id
            )
        ]
        if len(member_nodes) != 1:
            raise ValidationError(self.env._(
                "%(record_name)s must occur exactly once in its Call Flow.",
                record_name=record.display_name,
            ))
        nodes_by_id = {
            node.get("id"): node
            for node in nodes
            if isinstance(node, dict) and node.get("id") is not None
        }
        target_nodes = self._get_graph_output_nodes(
            member_nodes[0], output_ids, nodes_by_id, connections
        )
        return {
            output_id: self._get_node_pbx_destination(
                target_node, {self.id}, recovery=recovery,
            )
            for output_id, target_node in target_nodes.items()
        }

    def _get_time_condition_output_pbx_destinations(self, time_condition, recovery=False):
        destinations = self._get_record_output_pbx_destinations(
            time_condition, ("open", "closed"), recovery=recovery,
        )
        hangup = {"type": "hangup", "cause": "normal"}
        return {
            output_id: destination or hangup
            for output_id, destination in destinations.items()
        }

    def _ensure_graph_users_exist_in_pbx(self):
        """Provision users referenced by the graph when the Call Flow is saved."""
        user_ids = set()
        for call_flow in self:
            graph_data = call_flow.graph_data or {}
            nodes = graph_data.get("nodes")
            if not isinstance(nodes, list):
                continue
            for node in nodes:
                record = node.get("record") if isinstance(node, dict) else None
                if (
                    isinstance(record, dict)
                    and record.get("resModel") == "res.users"
                    and isinstance(record.get("resId"), int)
                ):
                    user_ids.add(record["resId"])
        for user in self.env["res.users"].browse(user_ids).exists():
            user._sync_pbx_user()

    def _ensure_graph_sounds_exist_in_pbx(self):
        """Upload Sounds before synchronizing routes that use them."""
        sound_ids = set()
        for call_flow in self:
            graph_data = call_flow.graph_data or {}
            nodes = graph_data.get("nodes")
            if not isinstance(nodes, list):
                continue
            for node in nodes:
                record = node.get("record") if isinstance(node, dict) else None
                if (
                    isinstance(record, dict)
                    and record.get("resModel") == "voip.sound"
                    and isinstance(record.get("resId"), int)
                ):
                    sound_ids.add(record["resId"])
        self.env["voip.sound"].browse(sound_ids).exists().with_context(
            voip_raise_pbx_sync_error=True
        )._sync_pbx()

    def _get_first_node(self):
        """Validate and return the first business node of this Call Flow.

        Returns None if the Start node isn't connected to anything: that
        resolves to Hang Up, same as an explicit Hangup node, rather than
        blocking the phone number/route using this Call Flow as destination.
        """
        self.ensure_one()
        graph_data = self.graph_data or {}
        nodes = graph_data.get("nodes")
        connections = graph_data.get("connections")
        if not isinstance(nodes, list) or not isinstance(connections, list):
            raise ValidationError(
                self.env._("The Call Flow graph must contain nodes and connections.")
            )

        start_nodes = [
            node
            for node in nodes
            if isinstance(node, dict) and node.get("type") == "start"
        ]
        if len(start_nodes) != 1:
            raise ValidationError(
                self.env._("The Call Flow must contain exactly one Start node.")
            )
        start_node = start_nodes[0]

        start_connections = [
            connection
            for connection in connections
            if (
                isinstance(connection, dict)
                and connection.get("sourceNodeId") == start_node.get("id")
                and connection.get("sourcePortId") == "next"
            )
        ]
        if not start_connections:
            return None
        if len(start_connections) != 1:
            raise ValidationError(
                self.env._("The Start node must be connected to exactly one node.")
            )

        target_node_id = start_connections[0].get("targetNodeId")
        target_nodes = [
            node
            for node in nodes
            if isinstance(node, dict) and node.get("id") == target_node_id
        ]
        if len(target_nodes) != 1 or target_nodes[0].get("type") == "start":
            raise ValidationError(
                self.env._("The node connected after Start is invalid.")
            )
        return target_nodes[0]

    def _get_route_destination(self, node):
        record = node.get("record") if isinstance(node, dict) else None
        if not isinstance(record, dict):
            raise ValidationError(
                self.env._("The node connected after Start has no destination.")
            )
        res_model = record.get("resModel")
        res_id = record.get("resId")
        supported_models = dict(PBX_DESTINATION_MODELS)
        if res_model not in supported_models or not isinstance(res_id, int):
            raise ValidationError(
                self.env._("The node connected after Start has an invalid destination.")
            )
        destination = self.env[res_model].browse(res_id).exists()
        if not destination:
            raise ValidationError(
                self.env._("The destination connected after Start no longer exists.")
            )
        return destination

    def _get_node_pbx_destination(self, node, visited_call_flow_ids, recovery=False):
        if not node:
            return None
        if node.get("type") == "hangup":
            return {"type": "hangup", "cause": "normal"}
        if node.get("type") == "outcall":
            extension = str(node.get("data", {}).get("extension") or "").strip()
            extension = extension.removeprefix("+")
            if not extension.isdigit():
                raise ValidationError(self.env._(
                    "An Outcall node must contain a valid extension."
                ))
            return {"type": "outcall", "exten": extension}
        if node.get("type") == "time_condition":
            graph_data = self.graph_data or {}
            nodes_by_id = {
                graph_node.get("id"): graph_node
                for graph_node in graph_data.get("nodes") or []
                if isinstance(graph_node, dict) and graph_node.get("id") is not None
            }
            open_target = self._get_graph_output_nodes(
                node,
                ("open",),
                nodes_by_id,
                graph_data.get("connections") or [],
            )["open"]
            return self._get_node_pbx_destination(
                open_target, visited_call_flow_ids, recovery=recovery,
            )
        service = self.env["voip.pbx.service"]
        if recovery:
            return service._get_pbx_recovery_destination(
                self._get_route_destination(node), visited_call_flow_ids,
            )
        return service._get_pbx_destination(
            self._get_route_destination(node), visited_call_flow_ids,
        )

    def _resolve_pbx_destination(self, visited_call_flow_ids=None, recovery=False):
        self.ensure_one()
        if not self.active:
            return None
        # Only Call Flows recurse into another route. All other supported
        # destinations are terminal PBX payloads resolved by PBXService.
        visited_call_flow_ids = visited_call_flow_ids or set()
        if self.id in visited_call_flow_ids:
            raise ValidationError(
                self.env._("Call Flows cannot contain circular references.")
            )
        first_node = self._get_first_node()
        if first_node is None:
            return {"type": "hangup", "cause": "normal"}
        if first_node.get("type") == "time_condition":
            graph_data = self.graph_data or {}
            nodes_by_id = {
                node.get("id"): node
                for node in graph_data.get("nodes") or []
                if isinstance(node, dict) and node.get("id") is not None
            }
            first_node = self._get_graph_output_nodes(
                first_node,
                ("open",),
                nodes_by_id,
                graph_data.get("connections") or [],
            )["open"]
            if first_node is None:
                return {"type": "hangup", "cause": "normal"}
        return self._get_node_pbx_destination(
            first_node,
            visited_call_flow_ids | {self.id},
            recovery=recovery,
        )

    def _get_pbx_destination(self, visited_call_flow_ids=None):
        return self._resolve_pbx_destination(visited_call_flow_ids)

    def _get_pbx_recovery_destination(self, visited_call_flow_ids=None):
        return self._resolve_pbx_destination(
            visited_call_flow_ids, recovery=True,
        )

    def _get_pbx_incall_schedule_id(self):
        """Return the PBX schedule gating this Call Flow's inbound route."""
        self.ensure_one()
        if not self.active:
            return None
        first_node = self._get_first_node()
        if not first_node or first_node.get("type") != "time_condition":
            return None
        time_condition = self.env["voip.time.condition"].browse(
            first_node["record"]["resId"]
        ).exists()
        if not time_condition:
            return None
        if not time_condition.pbx_schedule_id:
            time_condition._sync_pbx()
        return time_condition.pbx_schedule_id or None
