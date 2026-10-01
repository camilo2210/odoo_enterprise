import { mailModels } from "@mail/../tests/mail_test_helpers";
import { Store } from "@mail/../tests/mock_server/store";

import { deserializeDate, serializeDate, today } from "@web/core/l10n/dates";

export class MailActivity extends mailModels.MailActivity {
    get_today_call_activities() {
        /** @type {import("mock_models").MailActivityType} */
        const MailActivityType = this.env["mail.activity.type"];
        const activityTypeIds = MailActivityType.search([["category", "=", "phonecall"]]);
        // mock: phone is not computed on activities, so it is not part of the domain
        const activities = this.browse(
            this.search([
                ["activity_type_id", "in", activityTypeIds],
                ["user_id", "=", this.env.uid],
                ["date_deadline", "<=", serializeDate(today())],
            ])
        );
        return new Store().add(activities, "_store_voip_fields").as_dict();
    }

    _store_voip_fields(res) {
        /** @type {import("mock_models").MailActivityType} */
        const MailActivityType = this.env["mail.activity.type"];
        /** @type {import("mock_models").MailTemplate} */
        const MailTemplate = this.env["mail.template"];
        /** @type {import("mock_models").ResPartner} */
        const ResPartner = this.env["res.partner"];

        // mock: _compute_phone / _mail_get_partners are not simulated, so pre-compute the related
        // record and partner per activity to derive phone, res_name and the linked partner.
        const recordByActivity = {};
        const partnerIdByActivity = {};
        for (const activity of this) {
            if (!activity.res_model || !activity.res_id) {
                continue;
            }
            const [record] = this.env[activity.res_model].search_read([
                ["id", "=", activity.res_id],
            ]);
            recordByActivity[activity.id] = record;
            if (activity.res_model === "res.partner") {
                partnerIdByActivity[activity.id] = activity.res_id;
            } else if (record?.partner_id) {
                partnerIdByActivity[activity.id] = record.partner_id;
            }
        }
        const phoneOf = (activity) => {
            if (activity.phone) {
                return activity.phone;
            }
            const record = recordByActivity[activity.id];
            if (record?.phone_formatted || record?.phone) {
                return record.phone_formatted || record.phone;
            }
            const partnerId = partnerIdByActivity[activity.id];
            if (!partnerId) {
                return undefined;
            }
            const [partner] = ResPartner.browse(partnerId);
            return partner?.phone_formatted || partner?.phone;
        };
        res.attr("activity_category", (activity) => {
            const [type] = activity.activity_type_id
                ? MailActivityType.browse(activity.activity_type_id)
                : [];
            return type ? type.category : activity.activity_category;
        });
        res.attr("date_deadline");
        res.many("mail_template_ids", ["name"], {
            value: (activity) => {
                const [type] = activity.activity_type_id
                    ? MailActivityType.browse(activity.activity_type_id)
                    : [];
                return MailTemplate.browse(type ? type.mail_template_ids : []);
            },
        });
        res.attr("phone", phoneOf);
        res.one("phone_country_id", "_store_voip_fields");
        res.extend(["res_id", "res_model"]);
        res.attr(
            "res_name",
            (activity) => activity.res_name || recordByActivity[activity.id]?.display_name
        );
        res.attr("state", (activity) =>
            this._compute_state_from_date(deserializeDate(activity.date_deadline))
        );
        res.attr("summary");
        res.one("user_id", (r) => r.one("partner_id", "_store_partner_fields"));
        res.one("partner", "_store_voip_fields", {
            predicate: (activity) => activity.res_model && activity.res_id,
            value: (activity) =>
                ResPartner.browse(
                    partnerIdByActivity[activity.id] ? [partnerIdByActivity[activity.id]] : []
                ),
        });
    }
}
