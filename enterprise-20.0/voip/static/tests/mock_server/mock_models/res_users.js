import { mailModels } from "@mail/../tests/mail_test_helpers";
import { fields, makeKwArgs } from "@web/../tests/web_test_helpers";

const ALLOWED_VOIP_BUS_MESSAGE_TYPES = [
    "voip/agent_state",
    "voip/request_agent_states",
    "voip.call.pull/initiate",
    "voip.call.pull/entry_failed",
    "voip.call.pull/suppress_invite",
    "voip.call.pull/pending_entries",
    "voip.call.pull/pending_entries_received",
    "voip.call.pull/result",
];

export class ResUsers extends mailModels.ResUsers {
    voip_provider_id = fields.Many2one({ relation: "voip.provider" });
    has_active_call = fields.Boolean({ default: false });
    should_display_in_call_im_status = fields.Boolean({ default: false });

    /** @override */
    _init_store_data(store) {
        const VoipCall = this.env["voip.call"];
        const VoipProvider = this.env["voip.provider"];
        /** @type {import("mock_models").ResUsers} */
        const ResUsers = this.env["res.users"];

        super._init_store_data(...arguments);
        const [user] = ResUsers.search_read([["id", "=", this.env.uid]]);
        if (user) {
            let [provider] = VoipProvider.search_read([["id", "=", user.voip_provider_id[0]]]);
            provider ??= {};
            store.add_global_values({
                voipConfig: {
                    didNumber: null,
                    didNumberFormatted: null,
                    didNumberState: null,
                    isInternalCallingProvisioned: false,
                    usesOdooProvider: Boolean(provider.is_odoo_provider),
                    mainNumber: null,
                    mainNumberFormatted: null,
                    missedCalls: VoipCall._get_number_of_missed_calls(),
                    mode: provider.mode || "demo",
                    outboundCallerId: null,
                    outboundCallerIdFormatted: null,
                    outboundNumbers: [],
                    sharedOutboundNumbers: [],
                    pbxExtensionNumber: null,
                    pbxAddress: provider.pbx_ip || "localhost",
                    recordingPolicy: provider.recording_policy || "disabled",
                    webSocketUrl: provider.ws_server || "ws://localhost",
                    voicemailCode: provider.voicemail_code || null,
                },
            });
        }
    }

    reset_last_seen_phone_call() {
        const domain = [("user_id", "in", [this.env.user.id])];
        const last_call = this.env["voip.call"].search(
            domain,
            makeKwArgs({
                limit: 1,
                order: "id DESC",
            })
        );
        this.env.user.last_seen_phone_call = last_call.id;
    }

    _store_voip_fields(res) {
        res.one("partner_id", "_store_partner_fields");
    }

    _store_im_status_fields(res) {
        super._store_im_status_fields(res);
        res.from_method("_store_has_active_call_fields");
    }

    _store_manual_im_status_fields(res) {
        super._store_manual_im_status_fields(res);
        res.from_method("_store_has_active_call_fields");
    }

    _store_has_active_call_fields(res) {
        // mock: should_display_in_call_im_status is a stored field tests set directly (py computes it
        // from has_active_call/manual_im_status); serialize the stored value.
        res.attr("should_display_in_call_im_status");
    }

    action_voip_bus_send(message_type, payload) {
        if (!ALLOWED_VOIP_BUS_MESSAGE_TYPES.includes(message_type)) {
            throw Error("Invalid VOIP message type.");
        }
        this.env["bus.bus"]._sendone("broadcast", message_type, payload);
    }
}
