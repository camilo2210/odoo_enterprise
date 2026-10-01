import { fields, Record } from "@mail/model/export";
import { _t } from "@web/core/l10n/translation";

export class Call extends Record {
    static _name = "voip.call";

    static getStatus({ isInProgress, state }) {
        switch (state) {
            case "aborted":
                return _t("Aborted");
            case "calling":
                return isInProgress ? _t("Ringing") : _t("Ended Unexpectedly");
            case "completed_elsewhere":
                return _t("Completed Elsewhere");
            case "ended_unexpectedly":
                return _t("Ended Unexpectedly");
            case "missed":
                return _t("Missed");
            case "ongoing":
                return isInProgress ? _t("Ongoing") : _t("Ended Unexpectedly");
            case "rejected":
                return _t("Rejected");
            case "terminated":
                return _t("Completed");
            default:
                return _t("Unknown");
        }
    }

    activity_id = fields.One("mail.activity");
    country_id = fields.One("res.country");
    create_date = fields.Datetime();
    /** @type {"incoming"|"outgoing"} */
    direction;
    /** @type {string} */
    display_name;
    /** @type {integer} */
    duration = 0;
    end_date = fields.Datetime();
    /** @type {boolean} */
    has_recording;
    partner_id = fields.One("res.partner");
    /** @type {import("@mail/core/country_model").Country | undefined} */
    phone_country_id = fields.One("res.country");
    /** @type {string} */
    phone_number;
    /** @type {string} */
    phone_number_formatted;
    start_date = fields.Datetime();
    /** @type {"aborted"|"calling"|"completed_elsewhere"|"ended_unexpectedly"|"missed"|"ongoing"|"rejected"|"terminated"} */
    state = "calling";
}

Call.register();
