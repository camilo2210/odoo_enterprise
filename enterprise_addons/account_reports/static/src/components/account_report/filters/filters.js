import { _t } from "@web/core/l10n/translation";

import { WarningDialog } from "@web/core/errors/error_dialogs";
import { DateTimeInput } from '@web/core/datetime/datetime_input';
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { formatDate, parseDate } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { ORM } from "@web/core/orm_plugin";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";
import { DialogPlugin } from "@web/core/dialog/dialog_plugin";
import { NotificationPlugin } from "@web/core/notifications/notification_plugin";

import { status, Component, proxy, useEffect, usePlugin } from "@odoo/owl";

import { AccountReportController } from "@account_reports/components/account_report/controller";

const { DateTime } = luxon;


export class AccountReportFilters extends Component {
    static template = "account_reports.AccountReportFilters";
    static components = {
        DateTimeInput,
        Dropdown,
        DropdownItem,
        MultiRecordSelector,
        RecordSelector,
    };

    orm = usePlugin(ORM);
    controller = usePlugin(AccountReportController);
    debugMode = usePlugin(DebugModePlugin);
    dialog = usePlugin(DialogPlugin);
    notification = usePlugin(NotificationPlugin);

    state = proxy({ dateFilter: this.initDateFilterState() });
    budgetName = proxy({
        value: "",
        invalid: false,
    });
    timeout = null;

    setup() {
        useEffect(() => {
            const reportId = this.controller.cachedFilterOptions()?.report_id;
            if (reportId !== this.dateFilterState.reportId) {
                this.state.dateFilter = this.initDateFilterState();
            }
        });
    }

    focusInnerInput(selectedItem) {
        selectedItem.el.querySelector(":scope input")?.focus();
    }

    //------------------------------------------------------------------------------------------------------------------
    // Getters
    //------------------------------------------------------------------------------------------------------------------
    get filterExtraOptionsData() {
        return {
            'all_entries': {
                'name': _t("Draft Entries"),
                'group': 'account_readonly',
                'show': this.controller.filters.show_draft,
            },
            'unreconciled': {
                'name': _t("Unreconciled Entries"),
                'show': this.controller.filters.show_unreconciled,
            },
            'include_analytic_without_aml': {
                'name': _t("Analytic Simulations"),
                'group': 'account_readonly',
            },
            'hierarchy': {
                'name': _t("Subtotals"),
                'show': this.controller.cachedFilterOptions().display_hierarchy_filter,
            },
            'unfold_all': {
                'name': _t("Unfold All"),
                'show': this.controller.filters.show_all,
            },
            'integer_rounding_enabled': {
                'name': _t("Integer Rounding"),
            },
            'consolidation': {
                'name': _t("Consolidation"),
                'show': this.controller.cachedFilterOptions().show_consolidation,
            },
            'hide_0_lines': {
                'name': _t("Hide lines at 0"),
                'ui_filter': true,
                'onSelect': () => this.toggleHideZeroLines(),
                'show': this.controller.filters.show_hide_0_lines !== "never",
            },
            'horizontal_split': {
                'name': _t("Split Horizontally"),
                'ui_filter': true,
                'onSelect': () => this.toggleHorizontalSplit(),
            },
        }
    }

    get selectedHorizontalGroupName() {
        for (const horizontalGroup of this.controller.cachedFilterOptions().available_horizontal_groups) {
            if (horizontalGroup.id === this.controller.cachedFilterOptions().selected_horizontal_group_id) {
                return horizontalGroup.name;
            }
        }
        return _t("None");
    }

    get isHorizontalGroupSelected() {
        return this.controller.cachedFilterOptions().available_horizontal_groups.some((group) => {
            return group.id === this.controller.cachedFilterOptions().selected_horizontal_group_id;
        });
    }

    get selectedTaxUnitName() {
        for (const taxUnit of this.controller.cachedFilterOptions().available_tax_units) {
            if (taxUnit.id === this.controller.cachedFilterOptions().tax_unit) {
                return taxUnit.name;
            }
        }
        return _t("Company Only");
    }

    get selectedVariantName() {
        for (const variant of this.controller.cachedFilterOptions().available_variants) {
            if (variant.id === this.controller.cachedFilterOptions().selected_variant_id) {
                return variant.name;
            }
        }
        return _t("None");
    }

    get selectedSectionName() {
        for (const section of this.controller.cachedFilterOptions().sections)
            if (section.id === this.controller.cachedFilterOptions().selected_section_id)
                return section.name;
    }

    get selectedAccountType() {
        let selectedAccountType = this.controller.cachedFilterOptions().account_type.filter(
            (accountType) => accountType.selected,
        );
        if (
            !selectedAccountType.length ||
            selectedAccountType.length === this.controller.cachedFilterOptions().account_type.length
        ) {
            return _t("All");
        }

        const accountTypeMappings = [
            { list: ["trade_receivable", "non_trade_receivable"], name: _t("All Receivable") },
            { list: ["trade_payable", "non_trade_payable"], name: _t("All Payable") },
            { list: ["trade_receivable", "trade_payable"], name: _t("Trade Partners") },
            { list: ["non_trade_receivable", "non_trade_payable"], name: _t("Non Trade Partners") },
        ];

        const listToDisplay = [];
        for (const mapping of accountTypeMappings) {
            if (
                mapping.list.every((accountType) =>
                    selectedAccountType.map((accountType) => accountType.id).includes(accountType),
                )
            ) {
                listToDisplay.push(mapping.name);
                // Delete already checked id
                selectedAccountType = selectedAccountType.filter(
                    (accountType) => !mapping.list.includes(accountType.id),
                );
            }
        }

        return listToDisplay
            .concat(selectedAccountType.map((accountType) => accountType.name))
            .join(", ");
    }

    get selectedAmlIrFilters() {
        const selectedFilters = this.controller.cachedFilterOptions().aml_ir_filters.filter(
            (irFilter) => irFilter.selected,
        );

        if (selectedFilters.length === 1) {
            return selectedFilters[0].name;
        } else if (selectedFilters.length > 1) {
            return _t("%s selected", selectedFilters.length);
        } else {
            return _t("None");
        }
    }

    get selectedPartnerFilters() {
        const options = this.controller.cachedFilterOptions();
        const partnersCount = options.partner_ids.length;
        const tagsCount = options.partner_categories.length;

        if (partnersCount && tagsCount) {
            return _t("Partners: %(partnersCount)s, Tags: %(tagsCount)s", { partnersCount, tagsCount });
        }
        else if (partnersCount) {
            return _t("Partners: %(partnersCount)s", { partnersCount });
        }
        else if (tagsCount) {
            return _t("Tags: %(tagsCount)s", { tagsCount });
        }
        else {
            return _t("Partners");
        }
    }

    get availablePeriodOrder() {
        return { descending: _t("Descending"), ascending: _t("Ascending") };
    }

    get periodOrder() {
        return this.controller.cachedFilterOptions().comparison.period_order === "descending"
            ? _t("Descending")
            : _t("Ascending");
    }

    get selectedExtraOptions() {
        const selectedExtraOptions = [];

        if (this.controller.cachedUserGroups.account_readonly && this.controller.filters.show_draft) {
            selectedExtraOptions.push(
                this.controller.cachedFilterOptions().all_entries
                    ? _t("With Draft Entries")
                    : _t("Posted Entries"),
            );
        }
        if (this.controller.filters.show_unreconciled && this.controller.cachedFilterOptions.unreconciled) {
            selectedExtraOptions.push(_t("Unreconciled Entries"));
        }
        if (this.controller.cachedFilterOptions().include_analytic_without_aml) {
            selectedExtraOptions.push(_t("Including Analytic Simulations"));
        }
        return selectedExtraOptions.join(", ");
    }

    get dropdownProps() {
        return {
            shouldFocusChildInput: false,
            hotkeys: {
                arrowright: (navigator) => this.focusInnerInput(navigator.activeItem),
            },
        };
    }

    get dateNavigationOptions() {
        /**
         * Returns custom navigation options to fully navigate the date options with your keyboard.
         */
        const findNearestDropdownItem = (navigator) => {
            for (let i = navigator.activeItemIndex; i >= 0; i--) {
                if (navigator.items[i].target.classList.contains("o-dropdown-item")) {
                    return navigator.items[i];
                }
            }
        };

        return {
            hotkeys: {
                arrowleft: (navigator) => {
                    if (!navigator.activeItem) {
                        return;
                    }
                    const periodType = findNearestDropdownItem(navigator)?.target.dataset.periodType;
                    if(this.dateFilterConfiguration.filters[periodType]) {
                        const filter = this.dateFilterConfiguration.filters[periodType];
                        this.selectNewPeriod(filter, -1);
                    }
                },
                arrowright: (navigator) => {
                    if (!navigator.activeItem) {
                        return;
                    }
                    const periodType = findNearestDropdownItem(navigator)?.target.dataset.periodType;
                    if(this.dateFilterConfiguration.filters[periodType]) {
                        const filter = this.dateFilterConfiguration.filters[periodType];
                        this.selectNewPeriod(filter, 1);
                    }
                },
                enter: {
                    callback: (navigator) => {
                        if (!navigator.activeItem) {
                            return;
                        }

                        const focusedElement = document.activeElement;
                        if (focusedElement.nodeName === "INPUT") {
                            for (const navigatorItem of navigator.items) {
                                if (navigatorItem.target.contains(focusedElement)) {
                                    navigatorItem.setActive();
                                    break;
                                }
                            }
                        }

                        const dropdownItem = findNearestDropdownItem(navigator)?.target;
                        const periodType = dropdownItem.dataset.periodType;

                        const inputField =
                            navigator.activeItem.target.nodeName === "INPUT"
                                ? navigator.activeItem.target
                                : dropdownItem.querySelector("input.o_input");

                        if(this.dateFilterState.editing === periodType) {
                            if(periodType === 'custom') {
                                // Not handled by the default writeDate
                                inputField?.blur();
                            }
                            else {
                                this.writeDate(this.dateFilterConfiguration.filters[periodType], inputField);
                            }
                        }
                        else {
                            this.selectDateFilter(periodType);
                        }

                        if(this.dateFilterState.editing === periodType) {
                            inputField.focus();
                        }
                    },
                    bypassEditableProtection: true,
                },
            },
            shouldFocusChildInput: false,
        };
    }

    get periodLabel() {
        return this.controller.cachedFilterOptions().comparison.number_period > 1 ? _t("Periods") : _t("Period");
    }
    //------------------------------------------------------------------------------------------------------------------
    // Helpers
    //------------------------------------------------------------------------------------------------------------------
    get hasAnalyticGroupbyFilter() {
        return Boolean(this.controller.cachedUserGroups.analytic_accounting) && (Boolean(this.controller.filters.show_analytic_groupby) || Boolean(this.controller.filters.show_analytic_plan_groupby));
    }

    isExtraOptionFilterShown(option) {
        let data = this.filterExtraOptionsData[option];
        return (
            option in this.controller.cachedFilterOptions() &&
            option in this.filterExtraOptionsData &&
            data.show !== false &&
            (data.group === undefined || this.controller.cachedUserGroups[data.group])
        );
    }

    get hasExtraOptionsFilter() {
        return Object.keys(this.filterExtraOptionsData)
                     .some(option => this.isExtraOptionFilterShown(option));
    }

    get hasUIFilter() {
        return Object.entries(this.filterExtraOptionsData)
                     .some(([option, data]) => data.ui_filter && this.isExtraOptionFilterShown(option));
    }

    get isBudgetSelected() {
        return this.controller.cachedFilterOptions().budgets?.some((budget) => {
            return budget.selected;
        });
    }

    updateReportLineComparison(resId) {
        const lines = this.controller.data()?.lines || [];
        const baseLine = lines.find((line) => line.columns[0].report_line_id === resId);

        if (baseLine) {
            this.filterClicked({
                optionKey: 'comparison',
                optionValue: {...this.controller.cachedFilterOptions().comparison, filter: 'report_line', base_report_line: {id: resId, name: baseLine.name}},
                reload: true,
            });
        }
        else {
            this.filterClicked({optionKey: 'comparison.filter', optionValue: 'no_comparison', reload: true});
        }
    }

    //------------------------------------------------------------------------------------------------------------------
    // Date filter
    //------------------------------------------------------------------------------------------------------------------

    dateFrom(optionKey) {
        return parseDate(this.controller.cachedFilterOptions()[optionKey].date_from, {tz: "UTC"});
    }

    dateTo(optionKey) {
        return parseDate(this.controller.cachedFilterOptions()[optionKey].date_to, {tz: "UTC"});
    }

    setCustomComparisonDate(type, date) {
        if (date) {
            this.controller.cachedFilterOptions().comparison[`date_${type}`] = typeof date === "string" ? date : date.toISODate();
            this.applyFilters('comparison');
        }
        else {
            this.dialog.add(WarningDialog, {
                title: _t("Odoo Warning"),
                message: _t("Date cannot be empty"),
            });
        }
    }

    computePeriodRange(date, startDay, startMonth, monthsPerPeriod) {
        /**
         * This function needs to stay consistent with the one inside account_return_type from module account_reports.
         * function_name = _get_period_boundaries
         */
        const alignedDate = date.minus({days: startDay - 1})
        let year = alignedDate.year;
        const monthOffset = alignedDate.month - startMonth;

        let periodNumber = Math.floor(monthOffset / monthsPerPeriod) + 1;

        if (date < DateTime.utc(year, startMonth, startDay)) {
            year -= 1;
            periodNumber = Math.floor((12 + monthOffset) / monthsPerPeriod) + 1;
        }

        let deltaMonth = periodNumber * monthsPerPeriod;

        const endDate = DateTime.utc(year, startMonth, 1).plus({ months: deltaMonth, days: startDay-2})
        const startDate = DateTime.utc(year, startMonth, 1).plus({ months: deltaMonth - monthsPerPeriod }).set({ day: startDay})
        return [startDate, endDate];
    }

    get dateOptions() {
        return this.controller.cachedFilterOptions().date;
    }

    get dateFilterState() {
        return this.state.dateFilter;
    }

    get isRangeMode() {
        return this.controller.cachedFilterOptions().filter_date.range_mode;
    }

    get selectedPeriodType() {
        // Returns the selected filter. Fallback is more prioritized if it is visible.
        if (this.dateOptions.fallback_from && this.isFilterVisible(this.dateOptions.fallback_from)) {
            return this.dateOptions.fallback_from;
        }

        return this.dateOptions.period_type;
    }

    get dateFilterConfiguration() {
        return this.controller.cachedFilterOptions().filter_date;
    }

    getDateFilterByPeriodType(periodType) {
        return this.dateFilterConfiguration.filters[periodType];
    }

    get selectedDateFilter() {
        if (this.selectedPeriodType === 'custom') {
            return {
                'key': 'custom',
            }
        }
        return this.getDateFilterByPeriodType(this.selectedPeriodType);
    }

    get availableDateFiltersSorted() {
        return Object.values(this.dateFilterConfiguration.filters).sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));
    }

    isFilterVisible(periodType) {
        return this.getDateFilterByPeriodType(periodType)?.always_shown || !this.getDateFilterByPeriodType(periodType)?.fallback;
    }

    isFilterDateSelected(periodType) {
        // Return true if the period type is the one currently used from the options.
        return this.selectedPeriodType === periodType;
    }

    initDateFilterState() {
        /** Creates the state object used to track current selected dates for each period type
         * Recomputed when the report_id is changed */
        const today = DateTime.utc().startOf("day");
        const dateTo = this.dateTo('date');
        const referenceDate = dateTo ?? today;

        let dateFrom = this.dateFrom('date');
        const selectedFilter = this.selectedDateFilter;

        if (!dateFrom && this.dateFilterConfiguration.range_mode) {
            dateFrom = this.computePeriodRange(referenceDate, selectedFilter.start_day, selectedFilter.start_month, selectedFilter.months_per_period)[0];
        }

        const newDateFilterState = {
            editing: false,
            reportId: this.controller.cachedFilterOptions().report_id,
        };

        for (const filter of this.availableDateFiltersSorted) {
            const filterName = filter.key

            if (filterName === 'today') {
                newDateFilterState.today = [false, today];
                continue;
            }

            // Selected filter stays aligned with the report's date_to.
            // Other filters fall back to today when today falls in range, this_year reports
            // have date_to at fiscal year-end, so month/quarter would otherwise default to
            // the last month/quarter of the year instead of the current one.
            let filterReferenceDate;
            if (this.isFilterDateSelected(filter.key)) {
                filterReferenceDate = referenceDate;
            } else {
                const todayInPeriod = !dateTo || (dateTo >= today && (!dateFrom || dateFrom <= today));
                filterReferenceDate = todayInPeriod ? today : referenceDate;
            }

            let range = this.findCustomRangeForDate(filter, filterReferenceDate)
                || this.computePeriodRange(filterReferenceDate, filter.start_day, filter.start_month, filter.months_per_period);

            if (!this.isRangeMode) {
                range[0] = false;
            }

            newDateFilterState[filterName] = range;
        }

        if (!newDateFilterState.custom) {
            newDateFilterState['custom'] = [dateFrom, dateTo];
        }

        return newDateFilterState;
    }

    getDateDescription() {
        return this.controller.cachedFilterOptions().date.string;
    }

    getFilterDateDisplay(filter) {
        const [dateFrom, dateTo, customLabel] = this.dateFilterState[filter.key];

        if (customLabel) return customLabel;
        if (filter.key === "today") return filter.label;

        const format = (d, fmt) => formatDate(d, fmt ? { format: fmt } : undefined);

        if (this.isRangeMode) {
            const isFullMonth = dateFrom.ts === dateFrom.startOf("month").ts && dateTo.ts === dateTo.endOf("month").startOf("day").ts;
            if (isFullMonth) {
                const isFullYear = isFullMonth && dateFrom.year === dateTo.year && dateFrom.month === 1 && dateTo.month === 12;
                if (isFullYear) return format(dateTo, "yyyy");
                const isSameMonth = dateFrom.month === dateTo.month && dateFrom.year === dateTo.year;
                return isSameMonth ? format(dateTo, "MMMM yyyy") : `${format(dateFrom, "MMM yyyy")} - ${format(dateTo, "MMM yyyy")}`;
            }
            return `${format(dateFrom)} - ${format(dateTo)}`
        }

        else {
            const periodType = filter.fallback || filter.key;
            const isEndOfMonth = dateTo.ts === dateTo.endOf("month").startOf("day").ts;
            if (isEndOfMonth && periodType === 'month') return format(dateTo, "MMMM yyyy");
            if (periodType === 'quarter') {
                const dateFormat = isEndOfMonth ? "MMM yyyy" : undefined;
                const dateFrom = this.getPeriodDates(dateTo, filter)[0];
                return `${format(dateFrom, dateFormat)} - ${format(dateTo, dateFormat)}`;
            }

            const isEndOfYear = dateTo.ts === dateTo.endOf("year").startOf("day").ts;
            if (isEndOfYear && periodType === 'year') return format(dateTo, "yyyy");

            return format(dateTo);
        }
    }

    selectDateFilter(periodType) {
        if (this.isFilterDateSelected(periodType)) {
            this.dateFilterState.editing = periodType;
            return;
        }

        const customName = this.dateFilterState[periodType].length === 3 ? this.dateFilterState[periodType][2] : undefined;
        this.applyNewPeriod(periodType, this.dateFilterState[periodType][0], this.dateFilterState[periodType][1], customName);
    }

    selectNewPeriod(filter, side) {
        let [dateFrom, dateTo] = this.dateFilterState[filter.key];
        const direction = Math.sign(side);

        if (!this.isRangeMode && direction === -1) {
            [dateFrom, dateTo] = this.getPeriodDates(dateTo, filter);
        }

        const reference = direction === 1 ? dateTo : dateFrom;
        const newPeriodDate = reference.plus({days: direction})
        const customRange = this.findCustomRangeForDate(filter, newPeriodDate);
        if (customRange) {
            this.applyNewPeriod(filter.key, customRange[0], customRange[1], customRange[2]);
            return;
        }

        let [newDateFrom, newDateTo] = this.computePeriodRange(newPeriodDate, filter.start_day, filter.start_month, filter.months_per_period);
        this.applyNewPeriod(filter.key, newDateFrom, newDateTo);
    }

    getPeriodDates(date, filter) {
        //Same utility function as the python one. it computes the period from a single date taking into account custom ranges.
        let periodType = filter.key;
        if (['today', 'custom'].includes(periodType)) {
            periodType = 'year';
        }

        filter = this.getDateFilterByPeriodType(periodType);

        const customRanges = this.findCustomRangeForDate(filter, date);
        if (customRanges) {
            return customRanges.slice(0, 2);
        }

        return this.computePeriodRange(date, filter.start_day, filter.start_month, filter.months_per_period);
    }

    findCustomRangeForDate(filter, date) {
        const customRanges  = filter.custom_ranges;

        if (!customRanges)
            return false;

        for (let [customRangeStart, customRangeEnd, customRangeName] of customRanges) {
            // Specify UTC as these are from odoo Database.
            customRangeStart = parseDate(customRangeStart, {tz: "UTC"});
            customRangeEnd = parseDate(customRangeEnd, {tz: "UTC"});

            if (date >= customRangeStart && date <= customRangeEnd) {
                return [customRangeStart, customRangeEnd, customRangeName];
            }
        }

        return false;
    }

    writeDate(filter, inputElement) {
        const inputText = inputElement?.value;
        if (!inputText || this.dateFilterState.editing !== filter.key) return;

        this.dateFilterState.editing = false;

        // Checks if the input text matches a custom range
        if (filter.custom_ranges) {
            const result = filter.custom_ranges.find((range) => range[2] === inputText);
            const tzOptions = { zone: "UTC", setZone: true };
            if (result) {
                this.applyNewPeriod(filter.key, DateTime.fromISO(result[0], tzOptions), DateTime.fromISO(result[1], tzOptions), result[2]);
                return;
            }
        }

        try {
            const [dateFrom, dateTo] = this.parseDateInput(filter, inputText);
            this.applyNewPeriod(filter.key, dateFrom, dateTo);
        }
        catch (error) {
            if (error.name !== "ConversionError") {
                throw error;
            }
        }
    }

    parseDateInput(filter, input) {
        // Dates are parsed as UTC because parsing them as local then converting them is error prone and weird
        const rawDateText = input.split("-").pop().trim();
        const tzOptions = { tz: "UTC" };
        let dateTo = undefined;

        if (rawDateText) {
            const formats = [
                "LLL yyyy",
                "LLLL yyyy",
                "yyyy",
                undefined,  //Full format
            ]

            let index = 0;
            while(!dateTo && index < formats.length) {
                try {
                    dateTo = parseDate(rawDateText, {...tzOptions, format: formats[index++]})
                }
                catch(error) {
                    if (error.name !== "ConversionError" || index >= formats.length) {
                        // ConversionError means it couldn't parse the input text, so we avoid throwing a traceback.
                        // We do nothing as the input field will automatically revert to the original input text.
                        throw error;
                    }
                }
            }
        }

        return this.computePeriodRange(dateTo, filter.start_day, filter.start_month, filter.months_per_period);
    }

    setCustomDateFrom(dateFrom) {
        this.dateFilterState['custom'][0] = dateFrom;
        this.changeDateOptions('custom', dateFrom, null);
    }

    setCustomDateTo(dateTo) {
        this.dateFilterState['custom'][1] = dateTo;
        this.changeDateOptions('custom', null, dateTo);
    }

    get customDateFrom() {
        return this.dateFilterState['custom'][0];
    }

    get customDateTo() {
        return this.dateFilterState['custom'][1];
    }

    applyNewPeriod(periodType, dateFrom, dateTo, customName) {
        this.dateFilterState[periodType] = customName ? [dateFrom, dateTo, customName] : [dateFrom, dateTo];
        let fallbackFrom = null;
        if (periodType !== "custom") {
            this.dateFilterState["custom"] = this.isRangeMode ? [dateFrom, dateTo] : [false, dateTo];

            const filter = this.getDateFilterByPeriodType(periodType);
            if (filter.fallback) {
                fallbackFrom = periodType;
                periodType = filter.fallback;
            }
        }

        // When changing the period of the date filter, unselect the 'Open On' filter by default.
        this.filterClicked({ optionKey: 'unreconciled', optionValue: false})

        this.changeDateOptions(periodType, this.isRangeMode ? dateFrom : false, dateTo, fallbackFrom)
    }

    changeDateOptions(periodType, dateFrom, dateTo, fallbackFrom) {
        if (dateFrom && typeof dateFrom !== "string") {
            dateFrom = dateFrom.toISODate();
        }

        if (dateTo && typeof dateTo !== "string") {
            dateTo = dateTo.toISODate();
        }

        const newDateOptions = {
            ...this.dateOptions,
            period_type: periodType ?? this.selectedPeriodType,
            date_from: dateFrom ?? this.dateOptions.date_from,
            date_to: dateTo ?? this.dateOptions.date_to,
            fallback_from: fallbackFrom,
        };

        this.filterClicked({
            optionKey: 'date',
            optionValue: newDateOptions,
            reload: true,
        });
    }

    //------------------------------------------------------------------------------------------------------------------
    // Number of periods
    //------------------------------------------------------------------------------------------------------------------
    setNumberPeriods(ev) {
        const numberPeriods = ev.target.value;

        if (numberPeriods >= 1)
            this.controller.cachedFilterOptions().comparison.number_period = parseInt(numberPeriods);
        else
            this.dialog.add(WarningDialog, {
                title: _t("Odoo Warning"),
                message: _t("Number of periods cannot be smaller than 1"),
            });
    }

    //------------------------------------------------------------------------------------------------------------------
    // Records
    //------------------------------------------------------------------------------------------------------------------
    getMultiRecordSelectorProps(resModel, optionKey) {
        return {
            resModel,
            resIds: this.controller.cachedFilterOptions()[optionKey],
            update: (resIds) => {
                this.filterClicked({ optionKey: optionKey, optionValue: resIds, reload: true});
            },
        };
    }

    get reportLineComparisonProps() {
        const { report_id } = this.controller.options();
        const comparison = this.controller.cachedFilterOptions()?.comparison || {};
        const resId = comparison.filter === 'report_line' ? comparison.base_report_line?.id || false : false;
        return {
            resModel: "account.report.line",
            domain: [["report_id", "=", report_id], ['expression_ids', '!=', false]],
            resId,
            update: (resId) => this.updateReportLineComparison(resId),
            fieldString: _t("Report Lines"),
        };
    }

    //------------------------------------------------------------------------------------------------------------------
    // Rounding unit
    //------------------------------------------------------------------------------------------------------------------
    roundingUnitName(roundingUnit) {
        return _t("In %s", this.controller.cachedFilterOptions().rounding_unit_names[roundingUnit]);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Generic filters
    //------------------------------------------------------------------------------------------------------------------
    filterClicked({ optionKey, optionValue = undefined, reload = false}) {
        if (optionValue !== undefined) {
            this.controller.updateOption(optionKey, optionValue);
        } else {
            this.controller.toggleOption(optionKey);
        }

        if (reload) {
            this.applyFilters(optionKey);
        }
    }

    applyFilters(optionKey = null, delay = 500) {
        // We only call the reload after the delay is finished, to avoid doing 5 calls if you want to click on 5 journals
        if (this.timeout) {
            clearTimeout(this.timeout);
        }

        const cacheKey = this.controller.getCacheKey(this.controller.cachedFilterOptions().sections_source_id,  this.controller.cachedFilterOptions().report_id);
        this.controller.loadingCallNumberByCacheKey[cacheKey] += 1;

        this.timeout = setTimeout(() => {
            if (status(this) !== "destroyed")
                this.controller.reload(optionKey, this.controller.cachedFilterOptions());
        }, delay);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Custom filters
    //------------------------------------------------------------------------------------------------------------------

    get companyName2Journals() {
        const mapping = this.controller.cachedFilterOptions().journals.reduce((map, journal) => {
            const companyName = journal.company_name;
            map[companyName] ??= [];
            map[companyName].push(journal);

            return map;
        }, {})

        return mapping;
    }

    selectGroup(group) {
        const wasSelected = group.selected;
        this._toggleRelatedJournals(group)
        this.controller.cachedFilterOptions().__journal_group_action = {
            action: wasSelected ? "remove" : "add",
            id: group.id,
        };
        // Toggle the selected status after the action is set
        group.selected = !wasSelected;
        this.applyFilters("journal_groups")
    }

    selectJournal(journal) {
        journal.selected = !journal.selected;
        this.applyFilters("journals");
    }

    _toggleRelatedJournals(selectedGroup) {
        this.controller.cachedFilterOptions().journals.forEach((journal) => {
            if (selectedGroup.journals.includes(journal.id)) {
                journal.selected = !journal.selected;
            }
        })
    }

    unfoldCompanyJournals(selectedCompanyName) {
        for (const journal of this.controller.cachedFilterOptions().journals) {
            if (journal.company_name === selectedCompanyName) {
                journal.unfolded = !journal.unfolded;
                journal.visible = !journal.visible;
            }
        }
    }

    async filterVariant(reportId) {
        this.controller.saveSessionOptions({
            ...this.controller.cachedFilterOptions(),
            selected_variant_id: reportId,
            sections_source_id: reportId,
        });
        await this.controller.displayReport(reportId);
    }

    async filterTaxUnit(taxUnit) {
        await this.filterClicked({ optionKey: "tax_unit", optionValue: taxUnit.id});
        this.controller.saveSessionOptions(this.controller.cachedFilterOptions());

        // force the company to those impacted by the tax units, the reload will be force by this function
        user.activateCompanies(taxUnit.company_ids);
    }

    async toggleHideZeroLines() {
        // Avoid calling the database when this filter is toggled; as the exact same lines would be returned; just reassign visibility.
        await this.controller.toggleOption("hide_0_lines", false);

        this.controller.saveSessionOptions(this.controller.cachedFilterOptions());
        this.controller.setLineVisibility(this.controller.data() ? this.controller.lines : []);
        this.controller.invalidateVisibleLines();  // since setLineVisibility update the stored lines
    }

    async toggleHorizontalSplit() {
        await this.controller.toggleOption("horizontal_split", false);
        this.controller.saveSessionOptions(this.controller.cachedFilterOptions());
        this.controller.invalidateVisibleLines();  // invalidate line heights (since horizontal split show/hide some lines)
    }

    async filterRoundingUnit(rounding) {
        await this.controller.updateOption('rounding_unit', rounding, false);

        this.controller.saveSessionOptions(this.controller.cachedFilterOptions());

        const minimalLines = this.controller.lines.map(line => ({
            unfolded: line.unfolded,
            columns: line.columns.map(column => ({
                no_format: column.no_format,
                figure_type: column.figure_type,
                format_params: column.format_params,
                is_zero: column.is_zero,
                blank_if_zero: column.blank_if_zero,
            })),
            column_percent_comparison_data: line.column_percent_comparison_data,
        }));

        const minimalFormattedLines = await this.orm.call(
            "account.report",
            "dispatch_report_action",
            [
                this.controller.cachedFilterOptions().report_id,
                this.controller.cachedFilterOptions(),
                "format_column_values_from_client",
                minimalLines,
            ],
            {
                context: this.controller.context,
            }
        );

        for (let i=0; i < this.controller.lines.length; i++) {
            const line = this.controller.lines[i];
            const new_line = minimalFormattedLines[i];
            for (let j=0; j < line.columns.length; j++) {
                line.columns[j].name = new_line.columns[j].name;
            }
            if (line.horizontal_group_total_data && new_line.horizontal_group_total_data) {
                line.horizontal_group_total_data.name = new_line.horizontal_group_total_data.name;
            }
            if (line.column_percent_comparison_data && new_line.column_percent_comparison_data) {
                line.column_percent_comparison_data.name = new_line.column_percent_comparison_data.name;
            }
        }
        this.controller.invalidateVisibleLines();
    }

    async selectHorizontalGroup(horizontalGroupId) {
        if (horizontalGroupId === this.controller.cachedFilterOptions().selected_horizontal_group_id) {
            return;
        }
        await this.filterClicked({ optionKey: "selected_horizontal_group_id", optionValue: horizontalGroupId, reload: true});
    }

    selectBudget(budget) {
        budget.selected = !budget.selected;
        this.applyFilters( 'budgets')
    }

    async createBudget() {
        const budgetName = this.budgetName.value.trim();
        if (!budgetName.length) {
            this.budgetName.invalid = true;
            this.notification.add(_t("Please enter a valid budget name."), {
                type: "danger",
            });
            return;
        }
        const createdId = await this.orm.call("account.report.budget", "create", [
            { name: budgetName },
        ]);
        this.budgetName.value = "";
        this.budgetName.invalid = false;
        const cachedFilterOptions = this.controller.cachedFilterOptions();
        this.controller.reload("budgets", {
            ...cachedFilterOptions,
            budgets: [
                ...cachedFilterOptions.budgets,
                // Selected by default if we don't have any horizontal group selected
                { id: createdId, selected: !this.isHorizontalGroupSelected },
            ],
        });
    }
}

registry.category("account_reports.default_components").add("AccountReportFilters", AccountReportFilters);
