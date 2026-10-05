/** @odoo-module **/

import { deserializeDate, formatDate, formatDateTime } from "@web/core/l10n/dates";
import { formatFloat } from "@web/views/fields/formatters";

const { DateTime } = luxon;

const DECLARATION_TYPES = ["Entry", "Mutation", "Withdrawal"];
const MISSING_VALUE = "XSDMISSING";
const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const DATETIME_REGEX = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/;

function isEmpty(value) {
    return value === undefined || value === null || value === false || value === "";
}

/**
 * Values missing from the declaration data are replaced by a placeholder: a dict
 * `{ _missing_: true, res_model, res_id, res_field, employee_id }` pointing to
 * the record field to complete, or the MISSING_VALUE string.
 */
export function isMissing(value) {
    return value === MISSING_VALUE || Boolean(value?._missing_);
}

/** Key of the missing value in the `missing_values` of the actionable warnings. */
export function getMissingKey(value) {
    return value?._missing_ ? `${value.res_model},${value.res_id},${value.res_field}` : "";
}

export function hasMissingValue(value) {
    if (isMissing(value)) {
        return true;
    }
    if (value && typeof value === "object") {
        return Object.values(value).some(hasMissingValue);
    }
    return false;
}

function toText(value) {
    return isEmpty(value) || isMissing(value) ? "" : String(value);
}

/**
 * Repeated Swissdec elements are serialized as lists, but a single occurrence
 * can come as a plain object.
 */
export function toList(value) {
    return (Array.isArray(value) ? value : [value]).filter((item) => !isEmpty(item));
}

/**
 * @param {Object[]|Object} notifications Swissdec notifications (NotificationType)
 * @param {"error"|"warning"|"info"} type
 */
export function toNotifications(notifications, type) {
    return toList(notifications).map((notification) => ({
        type,
        code: notification.DescriptionCode,
        qualityLevel: notification.QualityLevel,
        description: String(notification.Description ?? "").trim(),
    }));
}

/**
 * The declarations and the institution responses are raw JSON payloads: these
 * helpers display their values like regular fields (localized amounts and
 * dates). Values that do not have the expected shape are displayed as they are.
 */
export const swissdecFormat = {
    isMissing,

    amount(value) {
        const number = typeof value === "boolean" ? NaN : Number(value);
        if (isEmpty(value) || String(value).trim() === "" || !Number.isFinite(number)) {
            return toText(value);
        }
        return formatFloat(number, { digits: [16, 2] });
    },

    date(value) {
        if (typeof value === "string" && DATE_REGEX.test(value)) {
            const date = deserializeDate(value);
            if (date.isValid) {
                return formatDate(date);
            }
        }
        return toText(value);
    },

    dateTime(value) {
        // Institutions send their local (Swiss) time: display it without any
        // timezone conversion.
        if (typeof value === "string" && DATETIME_REGEX.test(value)) {
            const dateTime = DateTime.fromSQL(value);
            if (dateTime.isValid) {
                return formatDateTime(dateTime);
            }
        }
        return toText(value);
    },

    /**
     * xs:gYearMonth values: [year, month, tz] in the responses and
     * ["XSDGYEARMONTH", year, month, tz] in the declarations.
     */
    month(value) {
        if (isMissing(value)) {
            return "";
        }
        const [year, month] = toList(value).filter((part) => typeof part === "number");
        if (year && month) {
            return DateTime.fromObject({ year, month }).toFormat("LLLL yyyy");
        }
        return toList(value).join("-");
    },

    period(period) {
        return [swissdecFormat.date(period?.from), swissdecFormat.date(period?.until)].filter(Boolean).join(" → ");
    },

    personName(person) {
        return [person?.Lastname, person?.Firstname].map(toText).filter(Boolean).join(" ");
    },

    socialInsuranceNumber(person) {
        return toText(person?.["Social-InsuranceIdentification"]?.["SV-AS-Number"]);
    },

    taxAtSourceCode(category) {
        return category?.TaxAtSourceCode || category?.CategoryPredefined || category?.CategoryOpen || "";
    },

    /** Entries, mutations and withdrawals of a DeclarationCategory, single or repeated. */
    declarationEvents(declarationCategory) {
        return DECLARATION_TYPES.flatMap((type) =>
            toList(declarationCategory?.[type]).map((event) => ({
                type,
                reason: event.Reason,
                validAsOf: event.ValidAsOf,
            }))
        );
    },

    /**
     * Sum of an amount of table rows, like the aggregates of a list view.
     *
     * @param {Object[]} rows
     * @param {...string} path path of the amount in the `values` of the rows
     */
    total(rows, ...path) {
        let total = 0;
        let hasAmount = false;
        for (const row of rows) {
            const value = path.reduce((values, key) => values?.[key], row.values);
            const amount = Number(value);
            if (!isEmpty(value) && Number.isFinite(amount)) {
                total += amount;
                hasAmount = true;
            }
        }
        return hasAmount ? swissdecFormat.amount(Math.round(total * 100) / 100) : "";
    },
};
