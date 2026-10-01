import {
    Component,
    markup,
    onWillStart,
    onMounted,
    onWillUnmount,
    onPatched,
    proxy,
    signal,
    t,
    usePlugin,
    useProps,
} from "@odoo/owl";
import { useDebounced } from "@web/core/utils/timing";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { CopyButton } from "@web/core/copy_button/copy_button";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { Dialog } from "@web/core/dialog/dialog";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatList } from "@web/core/l10n/utils";
import { pyToJsLocale } from "@web/core/l10n/utils/locales";
import { KeepLast } from "@web/core/utils/concurrency";
import { TimesheetInlineForm } from "@timesheet_grid/components/timesheet_inline_form/timesheet_inline_form";
import { user } from "@web/core/user";
import { formatDurationTimesheet, roundTimeSpent } from "@timesheet_grid/utils/timer";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { DocumentationLink } from "@web/views/widgets/documentation_link/documentation_link";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";
import { FakeEventsPlugin } from "./fake_events_plugin";
import { TimesheetAssistantModel } from "./aw_timesheet_model";
import { TimesheetsAssistantTimeline } from "./timeline/timeline";
import { TimesheetsAssistantByProject } from "./by_project/by_project";

const { DateTime } = luxon;

export class TimesheetsAssistant extends Component {
    static components = {
        TimesheetInlineForm,
        Dropdown,
        DropdownItem,
        Dialog,
        DocumentationLink,
        TimesheetsAssistantTimeline,
        TimesheetsAssistantByProject,
    };
    static template = "timesheet_grid.TimesheetsAssistant";

    props = useProps(standardActionServiceProps);

    formatDuration = formatDurationTimesheet;
    suggestionsContentRef = signal.ref();

    debugMode = usePlugin(DebugModePlugin);
    fakeEvents = usePlugin(FakeEventsPlugin);

    setup() {
        this.keepLast = new KeepLast();
        const orm = useService("orm");
        const notification = useService("notification");
        this.dialog = useService("dialog");
        this.uiService = useService("ui");
        this.model = new TimesheetAssistantModel(
            { orm, notification, fakeEvents: this.fakeEvents },
            DateTime.now().startOf("day"),
            { onBeforeLoad: () => this.resetSelectionState() }
        );
        this.state = proxy({
            groupBy: localStorage.getItem("aw_suggestion_pref") || "timeline",
            showCreateForm: false,
            showAwayTime: localStorage.getItem("show_away_time") !== "false",
            connectionWarningDismissed:
                localStorage.getItem("aw_connection_warning_dismissed") === "true",
            webWatcherWarningDismissed:
                localStorage.getItem("aw_web_watcher_warning_dismissed") === "true",
            selectedRows: new Set(),
            isMouseButtonPressed: false,
            isSelectedRowDirty: false,
            isSelecting: false,
            focusedIndex: -1, // the currently highlighted row
            lastSelectedIndex: -1, // the anchor point for MAJ (Shift) selection
        });
        this.selectedTimesheet = null;
        this.pendingScrollToTimesheetId = null;

        onWillStart(async () => {
            await this.model.loadAssistantData();
            await this.keepLast.add(this.model.load());
        });

        this._onMouseUp = this.onMouseUp.bind(this);
        this._onMouseDownAll = this.onMouseDownAll.bind(this);
        this._onClickOutsideBound = this.onClickOutside.bind(this);
        this._onKeyDown = this.onKeyDown.bind(this);
        onMounted(() => {
            window.addEventListener("mouseup", this._onMouseUp);
            window.addEventListener("keydown", this._onKeyDown, { capture: true });
            window.addEventListener("mousedown", this._onMouseDownAll);
            const savedStep = localStorage.getItem("aw_install_wizard_step");
            if (savedStep === "2") {
                this.openInstallDialog(2);
            }
        });
        onWillUnmount(() => {
            window.removeEventListener("mouseup", this._onMouseUp);
            window.removeEventListener("keydown", this._onKeyDown);
            window.removeEventListener("mousedown", this._onMouseDownAll);
        });
        onPatched(() => {
            if (this.pendingScrollToTimesheetId !== null) {
                this.scrollToTimesheetForm(this.pendingScrollToTimesheetId);
            }
        });
        this.onTakeDebounced = useDebounced(this.onTake, 200);
    }

    get defaultSelectionState() {
        return {
            selectedRows: new Set(),
            isMouseButtonPressed: false,
            isSelectedRowDirty: false,
            isSelecting: false,
            focusedIndex: -1, // the currently highlighted row
            lastSelectedIndex: -1, // the anchor point for MAJ (Shift) selection
        };
    }

    /**
     * Reloading the model's data (day navigation, reconnect, sample-data generation) always
     * discards any in-progress selection/keyboard-nav state and closes the create form, since
     * the underlying suggestions it points to are about to be rebuilt from scratch. Wired as
     * the model's `onBeforeLoad` hook so it fires regardless of which path triggers a reload.
     */
    resetSelectionState() {
        Object.assign(this.state, this.defaultSelectionState, { showCreateForm: false });
    }

    get selectedRowCount() {
        return this.state.selectedRows.size;
    }

    get suggestionsTotal() {
        return this.model.data.totalDuration;
    }

    onClickOutside(ev) {
        const cards = document.querySelector(".o_suggestion");
        if (cards && !cards.contains(ev.target)) {
            this.initSelectedRows();
        }
    }

    onDateChange(ev) {
        this.model.data.currentDate = DateTime.fromISO(ev.target.value);
        this.model.fetchData();
    }

    navigateToDay(diff) {
        this.model.data.currentDate = this.model.data.currentDate.plus({ days: diff });
        this.model.fetchData();
    }

    navigateToToday() {
        this.model.data.currentDate = DateTime.now().startOf("day");
        this.model.fetchData();
    }

    get dayHeader() {
        const locale = pyToJsLocale(document.documentElement.getAttribute("lang")) || "en-US";
        const options = {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
        };
        return new Intl.DateTimeFormat(locale, options).format(this.model.data.currentDate);
    }

    get noSuggestionsText() {
        if (this.model.isToday) {
            return _t("No suggestions for %(boldStart)sToday%(boldEnd)s.", {
                boldStart: markup`<b>`,
                boldEnd: markup`</b>`,
            });
        } else {
            return _t("No suggestions for %(boldStart)s%(day)s%(boldEnd)s.", {
                boldStart: markup`<b>`,
                boldEnd: markup`</b>`,
                day: this.dayHeader,
            });
        }
    }

    keyFor(groupKey, title, start = false) {
        let key = null;
        if (this.state.groupBy === "timeline") {
            key = this.model.data.recordsByStart?.[start]?.key || null;
        } else {
            key = this.model.data.grouped[groupKey]?.suggestions?.[title]?.key || null;
        }
        const res = {
            groupKey,
            title,
            key,
        };
        if (this.state.groupBy === "timeline") {
            res.start = start;
        }
        return JSON.stringify(res);
    }

    disableTextSelection() {
        document.body.style.userSelect = "none";
    }

    enableTextSelection() {
        document.body.style.userSelect = "";
    }

    isSelected(groupKey, title, start = false) {
        return this.state.selectedRows.has(this.keyFor(groupKey, title, start));
    }

    isSameRecord(record, groupKey, title, start = false) {
        if (this.state.groupBy === "timeline") {
            return record.start === start;
        }
        return record.groupKey === groupKey && record.title === title;
    }

    get records() {
        return Object.values(this.model.data.recordsByStart);
    }

    get visualRecords() {
        if (this.state.groupBy === "project") {
            return Object.keys(this.model.data.grouped)
                .sort()
                .flatMap((groupKey) =>
                    Object.values(this.model.data.grouped[groupKey].suggestions).map((item) => ({
                        ...item,
                        groupKey: groupKey,
                    }))
                )
                .filter((a) => a.type !== "afk");
        }
        return this.records;
    }

    /**
     * @param {KeyboardEvent} ev
     */
    onKeyDown(ev) {
        if (ev.key === "Escape") {
            this.dismissAllForms();
            if (document.activeElement) {
                document.activeElement.blur();
            }
            return;
        }
        if (ev.target.closest(".o_timesheet_inline_form,.o_dialog") || !this.visualRecords.length) {
            return;
        }
        // Arrows: move focus | Space: toggle selection (sets anchor)
        // Shift + Arrows: select continuous range from anchor to focus
        // Esc: discard all selections and close form
        const records = this.visualRecords;

        if (ev.key === " " || ev.key === "Enter") {
            if (ev.target.classList.contains("o_suggestions_suggestion")) {
                ev.preventDefault();
            }
            if (ev.key === "Enter") {
                if (this.state.selectedRows.size > 0 && !this.state.showCreateForm) {
                    this.state.showCreateForm = true;
                }
                return;
            }
            if (this.state.focusedIndex !== -1) {
                const record = records[this.state.focusedIndex];
                this.state.lastSelectedIndex = this.state.focusedIndex;
                this.toggleSelect(record.groupKey, record.title, false, record.start);
            }
            return;
        } else if (ev.key === "ArrowUp" || ev.key === "ArrowDown") {
            ev.preventDefault();
            let newIndex = this.state.focusedIndex;

            if (ev.key === "ArrowDown") {
                newIndex = Math.min(records.length - 1, newIndex + 1);
            } else if (ev.key === "ArrowUp") {
                newIndex = Math.max(0, newIndex === -1 ? records.length - 1 : newIndex - 1);
            }
            if (newIndex !== this.state.focusedIndex) {
                if (!ev.shiftKey) {
                    this.state.focusedIndex = newIndex;
                    this.state.lastSelectedIndex = newIndex;
                } else {
                    const fallbackAnchor =
                        this.state.focusedIndex !== -1 ? this.state.focusedIndex : 0;
                    const anchor =
                        this.state.lastSelectedIndex === -1
                            ? fallbackAnchor
                            : this.state.lastSelectedIndex;

                    this.state.focusedIndex = newIndex;
                    this.selectRange(anchor, newIndex, false);
                }
                const container = this.suggestionsContentRef();
                if (!container) {
                    return;
                }
                const elements = container.querySelectorAll(".o_suggestions_suggestion");
                const element = elements[newIndex];
                if (!element) {
                    return;
                }
                element.focus({ preventScroll: true });
                element.scrollIntoView({ block: "nearest", behavior: "auto" });
            }
        }
    }

    selectRange(startIndex, endIndex, autoOpenForm = true) {
        this.clearSelectedTimesheet();
        const records = this.visualRecords;
        const start = Math.min(startIndex, endIndex);
        const end = Math.max(startIndex, endIndex);
        for (let i = start; i <= end; i++) {
            const record = records[i];
            const key = this.keyFor(record.groupKey, record.title, record.start);
            this.state.selectedRows.add(key);
        }
        if (this.state.selectedRows.size > 0) {
            if (autoOpenForm) {
                this.state.showCreateForm = true;
            }
            if (this.currentRecord) {
                this.updateRecordInForm();
            }
        } else {
            this.state.showCreateForm = false;
        }
    }

    getSelectionClass(groupKey, title, previousWasSelected, start = false) {
        let cssClasses = "";
        const isSelected = this.isSelected(groupKey, title, start);
        if (isSelected) {
            cssClasses = previousWasSelected
                ? "o_isSelected border-top-0 border border-info z-1"
                : "o_isSelected border border-info z-1";
        } else {
            cssClasses = "bg-view";
        }
        const records = this.visualRecords;
        if (this.state.focusedIndex !== -1 && records[this.state.focusedIndex]) {
            const focusedRecord = records[this.state.focusedIndex];
            if (this.isSameRecord(focusedRecord, groupKey, title, start)) {
                if (!isSelected) {
                    cssClasses = cssClasses.replace("bg-view", "o_keyboard_focused");
                } else {
                    cssClasses += " o_keyboard_focused";
                }
            }
        }
        return cssClasses;
    }

    onMouseDown(groupKey, title, ev, start = false) {
        this.state.isMouseButtonPressed = true;

        if (ev && ev.button !== 0) {
            return;
        }

        if (ev?.target.closest(".btn")) {
            return; // click on Take/Delete btns
        }
        this.disableTextSelection();
        this.state.isSelecting = true;
        const records = this.visualRecords;
        const clickedIndex = records.findIndex((r) => this.isSameRecord(r, groupKey, title, start));
        if (ev?.shiftKey && this.state.lastSelectedIndex !== -1) {
            this.selectRange(this.state.lastSelectedIndex, clickedIndex);
            this.state.focusedIndex = clickedIndex;
        } else {
            this.state.focusedIndex = clickedIndex;
            this.state.lastSelectedIndex = clickedIndex;
            this.toggleSelect(groupKey, title, true, start);
        }
    }

    onMouseEnter(groupKey, title, start = false) {
        /*
        When hovering over suggestion with the mouse button pressed, the new suggestions are not added to the form
        directly. Their data is first stored inside the state.selectRow, then once the user release the mouse button
        the update is done. This way only one update is triggered for the view form with the batch suggestion. This
        avoids overloading the server since we have only one update per batch selection instead of one update per hover.
        */
        if (this.state.isMouseButtonPressed) {
            if (this.state.selectedRows.size === 0) {
                this.onMouseDown(groupKey, title, undefined, start);
            } else {
                this.clearSelectedTimesheet();
                const key = this.keyFor(groupKey, title, start);
                if (this.state.selectedRows.has(key)) {
                    this.state.selectedRows.delete(key);
                    if (this.state.selectedRows.size === 0) {
                        this.dismissAllForms();
                        this.state.isSelectedRowDirty = false;
                    }
                } else {
                    this.state.selectedRows.add(key);
                    this.state.isSelectedRowDirty = true;
                }
            }
            return;
        }
        if (!(this.state.isSelecting && this.state.selectedTimesheet)) {
            return;
        }
        this.clearSelectedTimesheet();
        const key = this.keyFor(groupKey, title, start);
        if (!this.state.selectedRows.has(key)) {
            this.state.selectedRows.add(key);
        }
    }

    onMouseDownAll() {
        this.state.isMouseButtonPressed = true;
    }

    onMouseUp() {
        if (this.state.isSelectedRowDirty) {
            this.state.isSelectedRowDirty = false;
            this.updateRecordInForm();
        }
        this.state.isMouseButtonPressed = false;
        this.state.isSelecting = false;
        this.enableTextSelection();
    }

    toggleSelect(groupKey, title, autoOpenForm = true, start = false) {
        this.clearSelectedTimesheet();
        const key = this.keyFor(groupKey, title, start);
        if (this.state.selectedRows.has(key)) {
            this.state.selectedRows.delete(key);
            if (this.state.selectedRows.size === 0) {
                this.state.showCreateForm = false;
            } else {
                this.updateRecordInForm();
            }
        } else {
            this.state.selectedRows.add(key);
            if (autoOpenForm && !this.state.showCreateForm) {
                this.state.showCreateForm = true;
            } else if (this.currentRecord) {
                this.updateRecordInForm();
            }
        }
    }

    updateRecordInForm() {
        if (!this.currentRecord) {
            return;
        }
        const selectedData = this.selectedData;
        const vals = {
            name: selectedData.name,
            unit_amount: selectedData.unit_amount,
        };
        if (selectedData.project_id && this.model.projectById[this.selectedData.project_id]) {
            vals.project_id = {
                id: selectedData.project_id,
                display_name: this.model.projectById[this.selectedData.project_id]?.name,
            };
        }
        if (selectedData.task_id && this.model.taskById[this.selectedData.task_id]) {
            vals.task_id = {
                id: selectedData.task_id,
                display_name: this.model.taskById[this.selectedData.task_id],
            };
        }
        this.currentRecord.update(vals);
    }

    initSelectedRows() {
        this.state.selectedRows = new Set();
        this.state.focusedIndex = -1;
        this.state.lastSelectedIndex = -1;
    }

    getGroupedNames(selectedRows) {
        if (!selectedRows.length) {
            return "";
        }
        const selectedRecords = selectedRows
            .map((row) => {
                const { groupKey, title, start } = JSON.parse(row);
                if (this.state.groupBy === "timeline") {
                    return this.model.data.recordsByStart[start];
                }
                return this.model.data.grouped[groupKey]?.suggestions?.[title];
            })
            .filter(Boolean);
        const recordsWithoutTemplate = selectedRecords.filter(
            (record) => record.template === undefined && record.description === undefined
        );
        const groupedRecords = Object.groupBy(
            selectedRecords.filter(
                (record) => record.template !== undefined || record.description !== undefined
            ),
            ({ template, description }) => description || template
        );
        const groupNames = [];
        for (const [template, records] of Object.entries(groupedRecords)) {
            let groupName = template;
            for (let i = 1; i < records[0].matches.length; i++) {
                const values = [
                    ...new Set(records.map((record) => record.matches[i] ?? "")),
                ].filter(Boolean);
                groupName = groupName.replace(`$${i}`, formatList(values));
            }
            groupNames.push(groupName);
        }
        groupNames.push(...recordsWithoutTemplate.map((record) => record.title));
        return groupNames.join("; ");
    }

    get selectedData() {
        if (this.selectedTimesheet) {
            return this.selectedTimesheet;
        }

        let project_id = this.currentRecord?.data?.project_id ?? false;
        let task_id = this.currentRecord?.data?.task_id ?? false;
        let totalAmount = 0.0;

        for (const row of this.state.selectedRows) {
            const { groupKey, title, start } = JSON.parse(row);
            const params = this.model.getSuggestionParams(
                groupKey,
                title,
                start,
                this.state.groupBy
            );

            if (!project_id && params.project_id) {
                project_id = params.project_id;
                task_id = params.task_id || false;
            }

            totalAmount += params.unit_amount;
        }

        const name = this.getGroupedNames(Array.from(this.state.selectedRows));
        const roundedAmount =
            roundTimeSpent({
                minutesSpent: totalAmount,
                ...this.model.roundingValues,
            }) / 60;

        return {
            project_id,
            task_id,
            name,
            unit_amount: roundedAmount,
            date: this.model.data.currentDate.toISO().split("T")[0],
            user_id: user.userId,
        };
    }

    get context() {
        const context = {};
        if (!this.selectedTimesheet && this.selectedData) {
            for (const [key, value] of Object.entries(this.selectedData)) {
                context[`default_${key}`] = value;
            }
        }
        return context;
    }

    onShowCreateForm() {
        this.dismissAllForms();
        this.state.showCreateForm = true;
    }

    async onTake(groupKey, title, start = false) {
        return this.model.onTake(groupKey, title, start, this.state.groupBy);
    }

    onDelete(groupKey, title, refresh = true, isConsumed = false, start = false) {
        return this.model.onDelete(groupKey, title, refresh, isConsumed, start, this.state.groupBy);
    }

    onDeleteSelected() {
        this.state.selectedRows.forEach((row) => {
            const { groupKey, title, start } = JSON.parse(row);
            this.onDelete(groupKey, title, true, false, start);
        });
        this.dismissAllForms();
        this.initSelectedRows();
    }

    onSaveTimesheetForm(timesheet) {
        const localConfigVals = this.model.getLocalConfigValsOnTake(timesheet.data);
        for (const row of this.state.selectedRows) {
            const { groupKey, title, start } = JSON.parse(row);
            const matchKey = this.model.getMatchKey(groupKey, title, start, this.state.groupBy);
            this.onDelete(groupKey, title, false, true, start);

            this.model.frequencyViewerLocalConfig.addMatching(matchKey, localConfigVals);
        }

        this.model.addTimesheet(timesheet.data, this.state.selectedRows.size > 0);
        if (this.state.selectedRows.size > 0) {
            this.model.recordAssistantTimesheet(timesheet.data.id);
        }
        this.dismissAllForms();
    }

    onDeleteTimesheet(timesheetId) {
        this.model.removeTimesheet(timesheetId);
        this.dismissAllForms();
    }

    onClickExistingTimesheet(timesheet) {
        // Check if there's a currently selected timesheet with unsaved changes
        if (this.selectedTimesheet && this.currentRecord && this.currentRecord.dirty) {
            this.dialog.add(ConfirmationDialog, {
                body: _t("Do you want to save your changes?"),
                confirmLabel: _t("Save"),
                confirm: async () => {
                    if (await this.currentRecord.save()) {
                        this.onWriteTimesheet(this.currentRecord);
                        this.switchToTimesheet(timesheet);
                    }
                },
                cancel: () => {},
                close: () => {
                    this.switchToTimesheet(timesheet);
                },
            });
            return;
        }

        this.switchToTimesheet(timesheet);
    }

    switchToTimesheet(timesheet) {
        this.dismissAllForms();
        this.selectedTimesheet = timesheet;
        timesheet.showEditForm = true;
        this.state.isSelecting = true;

        // Mark that we need to scroll to this form when onPatched
        this.pendingScrollToTimesheetId = timesheet.id;
        this.initSelectedRows();
    }

    scrollToTimesheetForm(id) {
        const formEl = document.querySelector(`[data-timesheet-form="${id}"]`);
        if (formEl) {
            formEl.scrollIntoView({
                behavior: "smooth",
                block: "center",
                container: "nearest",
            });
            this.pendingScrollToTimesheetId = null;
        }
    }

    clearSelectedTimesheet() {
        if (this.selectedTimesheet) {
            this.selectedTimesheet.showEditForm = false;
            this.selectedTimesheet = null;
            this.state.isSelecting = false;
        }
        if (!this.state.showCreateForm) {
            this.currentRecord = null;
        }
    }

    dismissAllForms() {
        this.state.showCreateForm = false;
        this.state.isSelecting = false;
        this.clearSelectedTimesheet();
        this.initSelectedRows();
    }

    onWriteTimesheet(timesheet) {
        this.dismissAllForms();
        this.model.updateTimesheet(timesheet.data);
    }

    async generateSampleData() {
        return this.model.generateSampleData();
    }

    async onLinkedRecordSaved() {
        const editedTimesheetId = this.selectedTimesheet?.id;
        await this.keepLast.add(this.model.loadTimesheets());
        const timesheet = this.model.data.timesheets.find((ts) => ts.id === editedTimesheetId);
        if (timesheet) {
            this.switchToTimesheet(timesheet);
        } else {
            this.clearSelectedTimesheet();
        }
    }

    openInstallDialog(initialStep) {
        const savedStep = localStorage.getItem("aw_install_wizard_step");
        const step = initialStep || (savedStep ? parseInt(savedStep, 10) : 1);
        this.dialog.add(InstallTimesheetAssistantDialog, {
            onInstall: (os) => this.onInstallTimesheetAssistant(os),
            onTestConnection: () => this.testAwConnection(),
            initialStep: step,
        });
    }

    async onInstallTimesheetAssistant(os) {
        let url;
        if (os === "linux_jammy") {
            url = "https://nightly.odoo.com/aw/ubuntu/jammy/activitywatch-odoo-jammy.deb";
        } else if (os === "linux_noble") {
            url = "https://nightly.odoo.com/aw/ubuntu/noble/activitywatch-odoo-noble.deb";
        } else {
            url = "https://nightly.odoo.com/aw/windows/activitywatch-odoo_patched-latest-setup.exe";
        }

        const a = document.createElement("a");
        a.href = url;
        a.download = "";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    openTestConnectionDialog() {
        this.dialog.add(TestConnectionDialog, {
            awServerStatus: this.model.data.awServerStatus,
            onInstall: (os) => this.onInstallTimesheetAssistant(os),
            onTestConnection: () => this.testAwConnection(),
            openAppsOnDeviceDialog: () => this.openAppsOnDeviceDialog(),
            activeProjectName: this.model.data.activeProjectName,
            activeProjectSince: this.model.data.activeProjectSince,
        });
    }

    toggleShowAwayTime() {
        const currentShowAwayTime = this.state.showAwayTime;
        this.state.showAwayTime = !currentShowAwayTime;
        localStorage.setItem("show_away_time", (!currentShowAwayTime).toString());
    }

    onDismissConnectionWarning() {
        this.state.connectionWarningDismissed = true;
        localStorage.setItem("aw_connection_warning_dismissed", "true");
    }

    onDismissWebWatcherWarning() {
        this.state.webWatcherWarningDismissed = true;
        localStorage.setItem("aw_web_watcher_warning_dismissed", "true");
    }

    onGroupByChange(state) {
        this.initSelectedRows();
        this.dismissAllForms();
        this.state.groupBy = state;
        localStorage.setItem("aw_suggestion_pref", state);
    }

    openAppsOnDeviceDialog() {
        this.dialog.add(AppsOnDevicePermissionDialog);
    }

    async testAwConnection() {
        return this.model.testAwConnection();
    }
}

// Dialog Component
class InstallTimesheetAssistantDialog extends Component {
    static template = "timesheet_grid.InstallTimesheetAssistantDialog";
    static components = { CopyButton, Dialog };

    props = useProps({
        close: t.function(),
        onInstall: t.function(),
        onTestConnection: t.function(),
        initialStep: t.number().optional(),
    });

    setup() {
        this.state = proxy({
            showDevList: false,
            step: this.props.initialStep || 1,
        });
    }

    get os() {
        const userAgent = navigator.userAgent || "";
        let platform = navigator.platform || "";

        if (navigator.userAgentData && navigator.userAgentData.platform) {
            platform = navigator.userAgentData.platform;
        }

        platform = platform.toLowerCase();
        if (platform.includes("win") || /windows/i.test(userAgent)) {
            return "windows";
        } else if (
            (platform.includes("linux") || /linux/i.test(userAgent)) &&
            !/android/i.test(userAgent)
        ) {
            return "linux";
        } else if (platform.includes("mac") || /mac/i.test(userAgent)) {
            return "mac";
        } else {
            return "unknown";
        }
    }

    onDevToggle() {
        this.state.showDevList = !this.state.showDevList;
    }

    onInstall(os) {
        this.props.onInstall(os);
    }

    onNext() {
        if (this.state.step < 6) {
            if (this.state.step === 1 && this.os === "windows") {
                this.state.step += 2;
            } else {
                this.state.step++;
            }
            this.saveStep();
        }
    }

    onPrev() {
        if (this.state.step > 1) {
            if (this.state.step === 3 && this.os === "windows") {
                this.state.step -= 2;
            } else {
                this.state.step--;
            }
            this.saveStep();
        }
    }

    saveStep() {
        localStorage.setItem("aw_install_wizard_step", this.state.step.toString());
    }

    onConfigureNow() {
        window.open("http://localhost:5600/#/settings", "_blank");
    }

    onDiscard() {
        if (this.state.step === 6) {
            localStorage.removeItem("aw_install_wizard_step");
        }
        this.props.close();
    }
}

class TestConnectionDialog extends Component {
    static template = "timesheet_grid.TestConnectionDialog";
    static components = { CopyButton, Dialog, DocumentationLink };

    props = useProps({
        close: t.function(),
        awServerStatus: t.string(),
        onInstall: t.function(),
        onTestConnection: t.function(),
        openAppsOnDeviceDialog: t.function(),
        activeProjectName: t.string().optional(),
        activeProjectSince: t.string().optional(),
    });

    get originUrl() {
        return window.location.origin;
    }

    get os() {
        const userAgent = navigator.userAgent || "";
        let platform = navigator.platform || "";

        if (navigator.userAgentData && navigator.userAgentData.platform) {
            platform = navigator.userAgentData.platform;
        }

        platform = platform.toLowerCase();
        if (platform.includes("win") || /windows/i.test(userAgent)) {
            return "windows";
        } else if (
            (platform.includes("linux") || /linux/i.test(userAgent)) &&
            !/android/i.test(userAgent)
        ) {
            return "linux";
        } else if (platform.includes("mac") || /mac/i.test(userAgent)) {
            return "mac";
        } else {
            return "unknown";
        }
    }

    onInstall(os) {
        this.props.onInstall(os);
    }

    onConfigureCORS() {
        window.open("http://localhost:5600/#/settings", "_blank");
    }

    onHelp() {}
}

export class AppsOnDevicePermissionDialog extends Component {
    static template = "timesheet_grid.AppsOnDevicePermissionDialog";
    static components = { Dialog };

    props = useProps({
        close: t.function(),
    });

    setup() {
        this.ui = useService("ui");
    }
}

registry.category("actions").add("hr_timesheet_activitywatch_action", TimesheetsAssistant);
