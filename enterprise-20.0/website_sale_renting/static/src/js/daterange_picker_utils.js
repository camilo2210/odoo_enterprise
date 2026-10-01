import {
    ConversionError, deserializeDateTime, parseDate, serializeDateTime
} from '@web/core/l10n/dates';
import { session } from '@web/session';

/**
 * Check whether the duration is computed in hours.
 *
 * @param {HTMLElement} el - The element containing the daterange picker.
 * @return {Boolean} - Whether the duration is computed in hours.
 */
function isDurationWithHours(el) {
    return el.dataset.rentalDurationUnit === 'hours';
}

/**
 * Get the date from the daterange input.
 *
 * @param {HTMLInputElement} input - The input element to get the date from.
 * @param {HTMLElement} el - The element containing the daterange picker.
 * @return {DateTime} - The date.
 */
function getDateFromInput(input, el) {
    try {
        return parseDate(input.value, { tz: session.website_tz });
    } catch (e) {
        if (!(e instanceof ConversionError)) {
            throw e;
        }
        return false;
    }
}

/**
 * Get the renting pickup and return dates from the daterange picker.
 *
 * @param {HTMLElement} el - The element containing the daterange picker.
 * @return {Object} - The renting pickup and return dates.
 */
function getRentalDates(el) {
    const startDateInput = el.querySelector('input[name=renting_start_date]');
    const endDateInput = el.querySelector('input[name=renting_end_date]');
    let startDate = getDateFromInput(startDateInput, el);
    let endDate = getDateFromInput(endDateInput, el);
    if (startDate && endDate) {
        const startDatetimeUTC = startDateInput.dataset.startDatetime
        const endDatetimeUTC = endDateInput.dataset.endDatetime
        if (startDatetimeUTC && endDatetimeUTC) {
            const startDatetime = deserializeDateTime(startDatetimeUTC, { tz: session.website_tz });
            const endDatetime = deserializeDateTime(endDatetimeUTC, { tz: session.website_tz });
            startDate = startDate.set({ hour: startDatetime.hour, minute: startDatetime.minute });
            endDate = endDate.set({ hour: endDatetime.hour, minute: endDatetime.minute });
        } else {
            // No startDatetime/endDatetime on the shop page if no dates are set
            startDate = startDate.startOf('day');
            endDate = endDate.endOf('day');
        }
    }
    return {
        startDate: startDate,
        endDate: endDate,
    };
}

/**
 * Get the serialized renting pickup and return dates from the daterange picker.
 *
 * Used for client-server exchange.
 *
 * @param {HTMLElement} el - The element containing the daterange picker.
 * @return {Object} - The serialized renting pickup and return dates.
 */
function getSerializedRentalDates(el) {
    const { startDate, endDate } = getRentalDates(el);
    if (startDate && endDate) {
        return {
            start_date: serializeDateTime(startDate),
            end_date: serializeDateTime(endDate),
        };
    }
    return {};
}

export default {
    isDurationWithHours: isDurationWithHours,
    getRentalDates: getRentalDates,
    getSerializedRentalDates: getSerializedRentalDates,
};
