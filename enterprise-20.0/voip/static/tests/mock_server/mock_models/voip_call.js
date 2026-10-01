import { Store } from "@mail/../tests/mock_server/store";

import { getKwArgs, makeKwArgs, models } from "@web/../tests/web_test_helpers";
import { deserializeDateTime, serializeDateTime, serializeDate, today } from "@web/core/l10n/dates";

export class VoipCall extends models.ServerModel {
    _name = "voip.call";

    create(attrs, kwargs) {
        const ids = super.create(...arguments);
        this.compute_effective_start_date(this.browse(ids));
        this.compute_end_date(this.browse(ids));
        return ids;
    }

    write(ids, data) {
        const result = super.write(...arguments);
        this.compute_effective_start_date(this.browse(ids));
        this.compute_end_date(this.browse(ids));
        return result;
    }

    /** @param {number[]} ids */
    abort_call(ids) {
        this.write(ids, { state: "aborted" });
        return this._get_result(ids);
    }

    /**
     * @param {number} res_id
     * @param {string} res_model
     */
    create_and_format(...kwargs) {
        kwargs = getKwArgs(arguments, "res_id", "res_model");
        const { res_id, res_model, context } = kwargs;
        if ("conversation_identifier" in kwargs) {
            // The wire carries the PBX identifier; the record holds the row.
            kwargs.conversation_id = this.env["voip.conversation"]._get_or_create(
                kwargs.conversation_identifier
            );
            delete kwargs.conversation_identifier;
        }
        if (!kwargs.activity_id && res_id && res_model) {
            const activityId = this._create_call_activity(res_model, res_id);
            if (activityId) {
                kwargs.activity_id = activityId;
            }
        }
        delete kwargs.res_id;
        delete kwargs.res_model;
        delete kwargs.context;
        const store_data = this._get_store_data(this.create(kwargs, makeKwArgs({ context })));
        return {
            ids: [store_data["voip.call"][0].id],
            store_data,
        };
    }

    get_by_id(call_id) {
        const recordIds = this.search([["id", "=", call_id]], makeKwArgs({ limit: 1 }));
        if (recordIds.length) {
            return {
                ids: recordIds,
                store_data: this._get_store_data(recordIds),
            };
        }
        return null;
    }

    get_or_create(data) {
        /** @type {import("./voip_call_leg").VoipCallLeg} */
        const VoipCallLeg = this.env["voip.call.leg"];
        /** @type {import("./voip_conversation").VoipConversation} */
        const VoipConversation = this.env["voip.conversation"];
        const id = data.id;
        const sip_call_id = data.sip_call_id;
        delete data.id;
        delete data.sip_call_id;
        if (id) {
            const recordIds = this.browse([id]);
            if (recordIds.length) {
                return {
                    ids: recordIds,
                    store_data: this._get_store_data(recordIds),
                };
            }
        }
        // Same order as the server: the PBX conversation when the INVITE
        // carried one, then the Call-ID through the legs. An outgoing call and
        // a non-Odoo provider reach this with no conversation at all.
        const conversationId = VoipConversation._get_or_create(data.conversation_identifier);
        let recordIds = conversationId
            ? this.search(
                  [
                      ["conversation_id", "=", conversationId],
                      ["state", "in", ["calling", "ongoing"]],
                  ],
                  makeKwArgs({ offset: 0, limit: 1 })
              )
            : [];
        if (!recordIds.length) {
            const callId = VoipCallLeg._find_call_id(sip_call_id);
            recordIds = callId ? [callId] : [];
        }
        if (!recordIds.length) {
            const created = this.create_and_format(
                makeKwArgs({
                    ...data,
                    control_handle: data.conversation_identifier || sip_call_id,
                })
            );
            VoipCallLeg._add_sip_call_id(created.ids[0], sip_call_id);
            return created;
        }
        VoipCallLeg._add_sip_call_id(recordIds[0], sip_call_id);
        return {
            ids: recordIds,
            store_data: this._get_store_data(recordIds),
        };
    }

    get_prefill_data() {
        // skip prefill by default
        // we implemented this method only because it called non-deterministically during runbot tests
        return {};
    }

    resolve_outgoing_dial_number(number) {
        return { number, is_internal: false };
    }

    compute_display_name(calls) {
        /** @type {import("./res_partner").ResPartner} */
        const ResPartner = this.env["res.partner"];
        const getName = (call) => {
            const preposition = call.direction === "incoming" ? "from" : "to";
            switch (call.state) {
                case "aborted":
                    return `Aborted call to ${call.phone_number}`;
                case "missed":
                    return `Missed call from ${call.phone_number}`;
                case "rejected":
                    return `Rejected call ${preposition} ${call.phone_number}`;
                default:
                    if (call.partner_id) {
                        const [partner] = ResPartner.search_read([["id", "=", call.partner_id]]);
                        return `Call ${preposition} ${partner.name}`;
                    }
                    return `Call ${preposition} ${call.phone_number}`;
            }
        };
        for (const call of calls) {
            call.display_name = getName(call);
        }
    }

    /**
     * @param {string} res_model
     * @param {number} res_id
     * @returns {number|boolean}
     */
    _create_call_activity(res_model, res_id) {
        /** @type {import("mock_models").MailActivityType} */
        const MailActivityType = this.env["mail.activity.type"];
        const activityTypeIds = MailActivityType.search([["category", "=", "phonecall"]]);
        if (!activityTypeIds.length) {
            return false;
        }
        const [activityId] = this.env["mail.activity"].create([
            {
                activity_type_id: activityTypeIds[0],
                res_model,
                res_id,
                date_deadline: serializeDate(today()),
                user_id: this.env.uid,
            },
        ]);
        return activityId;
    }

    miss_call(ids) {
        this.write(ids, { state: "missed" });
        return this._get_result(ids);
    }

    reject_call(ids) {
        this.write(ids, { state: "rejected" });
        return this._get_result(ids);
    }

    /**
     * @param {number[]} ids
     */
    end_call(ids) {
        const kwargs = getKwArgs(arguments, "ids");
        ids = kwargs.ids;
        const at = kwargs.at ? deserializeDateTime(kwargs.at) : luxon.DateTime.now();
        const calls = this.browse(ids);
        for (const call of calls) {
            if (!call.start_date) {
                // start_call has not run yet;
                // store at as a placeholder so start_call can compute duration.
                this.write([call.id], {
                    start_date: serializeDateTime(at),
                    duration: 0,
                    state: "terminated",
                });
            } else {
                const duration = at.diff(deserializeDateTime(call.start_date)).as("seconds");
                this.write([call.id], {
                    duration,
                    state: "terminated",
                });
            }
        }
        return this._get_result(ids);
    }

    compute_effective_start_date(calls) {
        for (const call of calls) {
            call.effective_start_date = call.start_date || call.create_date;
        }
    }

    compute_end_date(calls) {
        for (const call of calls) {
            if (call.start_date && call.duration) {
                call.end_date = serializeDateTime(
                    deserializeDateTime(call.start_date).plus({ seconds: call.duration })
                );
            } else {
                call.end_date = false;
            }
        }
    }

    _get_result(ids, success = true) {
        return { ids, success, store_data: this._get_store_data(ids) };
    }

    /** @param {number[]} ids */
    _get_store_data(ids) {
        if (!Array.isArray(ids)) {
            ids = [ids];
        }
        const records = this.browse(ids);
        this.compute_display_name(records);
        this.compute_effective_start_date(records);
        this.compute_end_date(records);
        return new Store().add(records, "_store_voip_fields").as_dict();
    }

    _store_voip_fields(res) {
        res.one("activity_id", "_store_voip_fields");
        res.one("country_id", "_store_voip_fields");
        res.extend(["create_date", "direction", "display_name", "duration", "has_recording"]);
        res.one("partner_id", "_store_voip_fields");
        res.one("phone_country_id", "_store_voip_fields");
        res.extend(["phone_number", "phone_number_formatted", "start_date", "state"]);
    }

    /** @param {number[]} ids */
    get_contact_info(ids) {
        /** @type {import("./res_partner").ResPartner} */
        const ResPartner = this.env["res.partner"];
        if (!Array.isArray(ids)) {
            ids = [ids];
        }
        const records = this.browse(ids);
        if (records.length !== 1) {
            throw new Error("self.ensure_one");
        }
        const [call] = records;
        const [partnerId] = ResPartner.search(
            [["phone", "=", call.phone_number]],
            makeKwArgs({ limit: 1 })
        );
        if (!partnerId) {
            return false;
        }
        this.write(ids, { partner_id: partnerId });
        return this._get_store_data(ids);
    }

    _get_number_of_missed_calls() {
        const domain = [
            ["user_id", "=", this.env.uid],
            ["state", "=", "missed"],
        ];
        if (this.env.user.last_seen_phone_call) {
            domain.push([("id", ">", this.env.user.last_seen_phone_call)]);
        }
        return this.search_count(domain);
    }

    /**
     * @param {number} [partner_id]
     * @param {number} [offset]
     * @param {number} [limit]
     */
    get_recent_phone_calls(direction, partner_id, offset = 0, limit) {
        const kwargs = getKwArgs(arguments, "direction", "partner_id", "offset", "limit");
        direction = kwargs.direction;
        partner_id = kwargs.partner_id;
        offset = kwargs.offset || 0;
        limit = kwargs.limit;
        const domain = [["user_id", "=", this.env.uid]];
        if (direction) {
            domain.push(["direction", "=", direction]);
        }
        if (partner_id) {
            domain.push(["partner_id", "=", partner_id]);
        }
        const recordIds = this.search(
            domain,
            makeKwArgs({
                offset,
                limit,
                order: "create_date DESC",
            })
        );
        return {
            ids: recordIds,
            store_data: this._get_store_data(recordIds),
        };
    }

    _get_prioritized_contact_ids(partnerDomain, limit) {
        if (!limit) {
            return [];
        }
        /** @type {import("./res_partner").ResPartner} */
        const ResPartner = this.env["res.partner"];
        const partnerMatches = new Set(ResPartner.search(partnerDomain));
        const lastCallDateByPartnerId = new Map();
        for (const call of this.browse(this.search([["user_id", "=", this.env.uid]]))) {
            if (!partnerMatches.has(call.partner_id)) {
                continue;
            }
            const createDate = deserializeDateTime(call.create_date);
            const lastCallDate = lastCallDateByPartnerId.get(call.partner_id);
            if (!lastCallDate || createDate > lastCallDate) {
                lastCallDateByPartnerId.set(call.partner_id, createDate);
            }
        }
        return [...lastCallDateByPartnerId]
            .sort(
                ([_partnerAId, lastCallDateA], [_partnerBId, lastCallDateB]) =>
                    lastCallDateB.toMillis() - lastCallDateA.toMillis()
            )
            .slice(0, limit)
            .map(([partnerId]) => partnerId);
    }

    /** @param {number[]} ids */
    start_call(ids) {
        const kwargs = getKwArgs(arguments, "ids");
        ids = kwargs.ids;
        const at = kwargs.at ? deserializeDateTime(kwargs.at) : luxon.DateTime.now();
        const calls = this.browse(ids);
        for (const call of calls) {
            if (call.state === "terminated") {
                // end_call ran first; start_date holds the end time as placeholder;
                // compute duration before overwriting it.
                const duration = call.start_date
                    ? Math.max(0, deserializeDateTime(call.start_date).diff(at).as("seconds"))
                    : 0;
                this.write([call.id], {
                    start_date: serializeDateTime(at),
                    duration,
                });
            } else {
                const updates = { state: "ongoing" };
                if (!call.start_date || at < deserializeDateTime(call.start_date)) {
                    updates.start_date = serializeDateTime(at);
                }
                this.write([call.id], updates);
            }
        }
        return this._get_result(ids);
    }
}
