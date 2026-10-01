import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { areDatesEqual, deserializeDateTime, serializeDateTime } from '@web/core/l10n/dates';
import { Time } from '@web/core/l10n/time';
import { rpc } from '@web/core/network/rpc';
import { session } from '@web/session';
import daterangePickerUtils from '@website_sale_renting/js/daterange_picker_utils';

const { DateTime } = luxon;

export class DaterangePicker extends Interaction {
    static selector = '.o_website_sale_daterange_picker';
    dynamicSelectors = {
        ...this.dynamicSelectors,
        _productEl: () => this.el.closest('.js_product'),
    };
    dynamicContent = {
        _root: { 't-on-combination_changed': this.checkDaterangeValidity },
        _productEl: { 't-on-product_changed': this.onProductChanged },
        '[name="rental_start_time"], [name="rental_end_time"]': { 't-on-change': this.onTimeChanged },
    };

    setup() {
        this.rentingAvailabilities = {};
        const productEl = this.el.closest('.js_product');
        this.productId = parseInt(
            productEl?.querySelector('button[name="add_to_cart"]')?.dataset?.productId
        ) || undefined;
        const { startDate, endDate } = daterangePickerUtils.getRentalDates(this.el);
        this.startDate = startDate;
        this.endDate = endDate;
        const defaultStartDate = DateTime.now().setZone(session.website_tz);
        const defaultEndDate = DateTime.now().setZone(session.website_tz).plus({years: 3});
        this.minDate = DateTime.min(defaultStartDate, this.startDate || defaultStartDate);
        this.maxDate = DateTime.max(defaultEndDate, this.endDate || defaultEndDate);
        // Only add the constraints on the cart page
        this.isCartRentalPeriodPicker = !!this.el.closest('.o_wsale_shorter_cart_summary');
    }

    /**
     * Load the renting constraints.
     *
     * I.e. the days on which no pickup or return can be processed, and the minimal rental
     * duration imposed by the minimum quantity of the products currently in the cart.
     */
    async willStart() {
        await this._updateRentingConstraints();
    }

    /**
     * Initialize the rental pickup and return dates and the daterange picker popup.
     */
    start() {
        this.el.querySelectorAll('.o_daterange_picker').forEach(
            (el) => this._initDaterangePickerPopup(el)
        );
        this.updateTimeSelectors(true);
        this.checkDaterangeValidity();
        if (this.isCartRentalPeriodPicker) {
            this.env.bus.addEventListener(
                'cart_amount_changed', () => this._updateRentingConstraints()
            );
        }
    }

    /**
     * Fetch and store the renting constraints (working days/hours and minimum rental duration).
     */
    async _updateRentingConstraints() {
        const constraints = await this.waitFor(rpc('/rental/product/constraints', {
            min_date: serializeDateTime(this.minDate),
            max_date: serializeDateTime(this.maxDate),
        }));
        this.hasRentalCalendar = constraints.has_rental_calendar;
        this.workingDaysAndHours = constraints.working_days_and_hours;
        this.minimumRentalDuration = constraints.minimum_rental_duration ?? null;
    }

    /**
     * Populate and show the pickup/return time selectors.
     *
     * @param {boolean} useDefault - Whether to select the time from the dataset
     *     start-datetime/end-datetime or from the selected option.
     */
    updateTimeSelectors(useDefault) {
        const timeSelectors = this.el.querySelector('#rental_time_selectors');
        if (!timeSelectors) return;

        if (this.startDate) this._populateTimeOptions('rental_start_time', useDefault);
        if (this.endDate) this._populateTimeOptions('rental_end_time', useDefault);

        // Display the time selectors only if both start and end dates are set.
        timeSelectors.classList.toggle('d-none', !(this.startDate && this.endDate));
    }

    onTimeChanged(event) {
        // Set the original changed time on the respective date
        const timeSelectName = event.target.name;
        const selectedTime = Time.from(event.target.value);
        this.setTimeOnDate(timeSelectName, selectedTime);

        if (!this.startDate || !this.endDate) return;
        // If the other date and time become invalid, adapt it.
        if (this.startDate.hasSame(this.endDate, 'day') && this.endDate <= this.startDate) {
            const startTimeSelector = this.el.querySelector('select[name="rental_start_time"]');
            const endTimeSelector = this.el.querySelector('select[name="rental_end_time"]');
            if (timeSelectName === 'rental_start_time') {
                // endTimeSelector's first option is skipped when populating on the same dates.
                // We can therefore reuse the same index to get the next value.
                endTimeSelector.selectedIndex = startTimeSelector.selectedIndex;
                this.setTimeOnDate('rental_end_time', Time.from(endTimeSelector.value));
            } else {
                // startTimeSelector's last option is skipped when populating on the same dates.
                // We can therefore reuse the same index to get the previous value.
                startTimeSelector.selectedIndex = endTimeSelector.selectedIndex;
                this.setTimeOnDate('rental_start_time', Time.from(startTimeSelector.value));
            }
        }
        this.el.dispatchEvent(new CustomEvent('daterange_picker_applied', {
            detail: { startDate: this.startDate, endDate: this.endDate }
        }));
    }

    /**
     * Populate the time selector options for a given date.
     *
     * Uses office hours for the selected date when a rental calendar is configured or falls back
     * to full 24h options. Hours are formatted according to the user's language preferences (e.g.
     * "3:00PM" or "15:00"). On the same start/end date, the boundary hours are excluded to prevent invalid
     * ranges.
     *
     * @param {string} timeSelectName - 'rental_start_time' or 'rental_end_time'
     * @param {boolean} useDefault - Whether to select the time from the date input's start/end-datetime
     */
    _populateTimeOptions(timeSelectName, useDefault) {
        const timeSelect = this.el.querySelector(`select[name=${timeSelectName}]`);
        const startInput = this.el.querySelector('input[name=renting_start_date]');
        const endInput = this.el.querySelector('input[name=renting_end_date]');
        const isStart = timeSelectName === 'rental_start_time';
        const dateInput = isStart ? startInput : endInput;
        if (!timeSelect || !dateInput || !this.startDate || !this.endDate) return;

        timeSelect.innerHTML = ''; // Clear existing options

        const date = DateTime.fromFormat(dateInput.value, 'D', {zone: session.website_tz});
        // Do not populate time options when the date has become invalid.
        // E.g.: a change of hours in the calendar affecting existing carts.
        if (this.hasRentalCalendar && !(date.toISODate() in this.workingDaysAndHours)) return;
        const times = this.hasRentalCalendar
            ? this.workingDaysAndHours[date.toISODate()].map((hourAndMinute) => Time.from(hourAndMinute))
            : Array.from({ length: 25 }, (_, i) => Time.from({ hour: i, minute: 0 }));

        const startTime = times.at(0);
        const endTime = times.at(-1);
        const isSameDate = this.startDate.hasSame(this.endDate, 'day');

        const datetimeUTC = isStart ? dateInput.dataset.startDatetime : dateInput.dataset.endDatetime;
        const datetime = deserializeDateTime(datetimeUTC, { tz: session.website_tz });
        const updatedDatetime = date.set({ hour: datetime.hour, minute: datetime.minute });

        for (const time of times) {
            if (isSameDate && isStart && time.equals(endTime)) continue;
            if (isSameDate && !isStart && time.equals(startTime)) continue;

            const option = document.createElement('option');
            const formattedTime = time.toString()
            option.value = formattedTime;
            option.text = formattedTime;
            if (useDefault && time.equals(Time.from(updatedDatetime))) {
                option.selected = true;
            }
            timeSelect.add(option);
        }
        if (timeSelect.value) {
            this.setTimeOnDate(timeSelectName, Time.from(timeSelect.value));
        }
    }

    /**
     * @param {string} timeSelectName - 'rental_start_time' or 'rental_end_time'
     * @param {Time} time - The selected time.
     */
    setTimeOnDate(timeSelectName, selectedTime) {
        const startInput = this.el.querySelector('input[name=renting_start_date]');
        const endInput = this.el.querySelector('input[name=renting_end_date]');
        const isStart = timeSelectName === 'rental_start_time';
        const dateInput = isStart ? startInput : endInput;
        const date = isStart ? this.startDate : this.endDate;
        if (!dateInput || !date) return;

        const newDate = date.set({ hour: selectedTime.hour, minute: selectedTime.minute });
        if (isStart) {
            dateInput.dataset.startDatetime = serializeDateTime(newDate);
            this.startDate = newDate;
        } else {
            dateInput.dataset.endDatetime = serializeDateTime(newDate);
            this.endDate = newDate;
        }
    }

    /**
     * Update the daterange picker's product id.
     *
     * @param {CustomEvent} event
     */
    async onProductChanged(event) {
        this.productId = event.detail.productId;
    }

    /**
     * Check whether the dates (not the hours) in the daterange picker are valid and display a message if not.
     */
    checkDaterangeValidity() {
        const valid = this.canBeRented(this.startDate, this.endDate, this.productId);
        this.el.dispatchEvent(new CustomEvent(
            'daterange_validity_changed', { detail: { isValid: valid }}
        ));
    }

    /**
     * Initialize the daterange picker popup.
     *
     * @param {HTMLElement} el
     */
    _initDaterangePickerPopup(el) {
        const dateTimeManager = this.services['datetime_picker'].create(
            {
                target: el,
                pickerProps: {
                    value: [this.startDate, this.endDate],
                    range: true,
                    type: 'date',
                    minDate: this.minDate,
                    maxDate: this.maxDate,
                    isDateValid: (date)=> this._isValidDate(date),
                    dayCellClass: (date) => this._isCustomDate(date).join(' '),
                    tz: session.website_tz,
                },
                onApply: (_) => {
                    const { startDate, endDate } = daterangePickerUtils.getRentalDates(this.el);
                    if (areDatesEqual([this.startDate, this.endDate], [startDate, endDate])) {
                        return;
                    }
                    this.startDate = startDate;
                    this.endDate = endDate;
                    this.updateTimeSelectors(false);
                    this.checkDaterangeValidity();
                    this.el.dispatchEvent(new CustomEvent(
                        'daterange_picker_applied',
                        { detail: { startDate: this.startDate, endDate: this.endDate }},
                    ));
                },
                getInputs: () => [
                    el.querySelector('input[name=renting_start_date]'),
                    el.querySelector('input[name=renting_end_date]'),
                ],
            },
        );
        this.datetimePickerState = dateTimeManager.state;
        this.registerCleanup(dateTimeManager.destroy);
    }

    /**
     * Check whether the date is valid.
     *
     * @param {DateTime} date
     * @return {Boolean} - Whether the date is valid.
     */
    _isValidDate(date) {
        if (
            (this.hasRentalCalendar && !(date.toISODate() in this.workingDaysAndHours))
            || this._isBelowMinimumRentalDuration(date)
        ) {
            return false;
        }
        return true;
    }

    /**
     * Check whether picking `date` as the return date would break the minimum quantity
     * constraint of the products currently in the cart.
     *
     * @param {DateTime} date
     * @return {Boolean}
     */
    _isBelowMinimumRentalDuration(date) {
        if (!this.isCartRentalPeriodPicker || this.minimumRentalDuration === null) {
            return false;
        }
        const state = this.datetimePickerState;
        const pickupDate = state?.value?.[0];
        if (!state?.range || state.focusedDateIndex !== 1 || !pickupDate) {
            return false;
        }
        const minimumReturnDate = pickupDate.plus({ seconds: this.minimumRentalDuration });
        return date.startOf('day') <= minimumReturnDate.startOf('day');
    }

    /**
     * Set Custom CSS to a given daterange picker cell.
     *
     * @param {DateTime} date
     */
    _isCustomDate(date) {
        const dateStart = this.startDate
            ? date.set({ hour: this.startDate.hour, minute: this.startDate.minute }) : date;
        // Don't add cssClass in the past
        if (dateStart <= luxon.DateTime.now()) {
            return [];
        }
        // Out of business hours
        if (this.hasRentalCalendar && !(date.toISODate() in this.workingDaysAndHours)) {
            return ['o_daterangepicker_closed'];
        }
        // Out of stock
        if (this.productId && this.rentingAvailabilities[this.productId]) {
            for (const interval of this.rentingAvailabilities[this.productId]) {
                // The interval starts after the date
                if (interval.start > dateStart) {
                    break;
                }
                // The interval ends after the date
                if (interval.end > dateStart && interval.quantity_available <= 0) {
                    return ['o_daterangepicker_danger'];
                }
            }
        }
        return [];
    }

    /**
     * Update the renting availabilities dict with the availabilities of the current product.
     *
     * @param {Boolean} [force]
     */
    async _updateRentingProductAvailabilities(force=false) {
        if (!this.productId || (!force && this.rentingAvailabilities[this.productId])) {
            return;
        }

        const availabilities = await this.waitFor(rpc('/rental/product/availabilities', {
            product_id: this.productId,
            min_date: serializeDateTime(this.minDate),
            max_date: serializeDateTime(this.maxDate),
        }));
        this.rentingAvailabilities[this.productId] = [];
        if (availabilities.renting_availabilities?.length) {
            this.rentingAvailabilities[this.productId] = availabilities.renting_availabilities.map(
                (rentingAvailabilities) => {
                    const { start, end, ...rest } = rentingAvailabilities;
                    return {
                        // Deserialize into the website timezone for proper formatting.
                        start: deserializeDateTime(start, { tz: session.website_tz }),
                        end: deserializeDateTime(end, { tz: session.website_tz }),
                        ...rest,
                    };
                }
            );
        }
        // `preparation_time` is only populated/used in website_sale_stock_renting. It has no effect
        // in website_sale_renting, but we keep it here for simplicity.
        this.preparationTime = availabilities.preparation_time;
        this.checkDaterangeValidity();
    }

    /**
     * Get if the rental dates are invalid.
     *
     * @param {DateTime} startDate
     * @param {DateTime} endDate
     * @param {Number} productId
     * @return {Boolean} - whether the rental dates are invalid.
     */
    canBeRented(startDate, endDate, productId = 0) {
        if (startDate && endDate) {
            if (this.hasRentalCalendar && !(startDate.toISODate() in this.workingDaysAndHours)) {
                return false;
            }
            if (this.hasRentalCalendar && !(endDate.toISODate() in this.workingDaysAndHours)) {
                return false;
            }
            if (endDate <= startDate) {
                return false;
            }
            if (startDate < luxon.DateTime.now().setZone(session.website_tz).startOf('day')) {
                return false;
            }
        } else if (
            // Require the dates to be set on the product page and the cart summary.
            this.el.closest('.js_product, .o_wsale_shorter_cart_summary')
        ) {
            return false;
        }
        let valid = true;
        const intervals = this.rentingAvailabilities?.[productId] || [];
        for (const interval of intervals) {
            if (interval.start < endDate) {
                const end = this._getExpectedEndDate(interval.end);
                if (end > startDate) {
                    if (interval.quantity_available <= 0) {
                        valid = false;
                        break;
                    }
                }
            } else {
                break;
            }
        }
        return valid;
    }

    _getExpectedEndDate(endDate) {
        return endDate;
    }
}

registry
    .category('public.interactions')
    .add('website_sale_renting.daterange_picker', DaterangePicker);
