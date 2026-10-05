/* global owl:readonly */

import { _t } from "@web/core/l10n/translation";

import { user } from "@web/core/user";
import { range } from "@web/core/utils/numbers";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { ORM } from "@web/core/orm_plugin";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { UIPlugin } from "@web/core/ui/ui_plugin";
import { DialogPlugin } from "@web/core/dialog/dialog_plugin";
import { useEnv } from "@web/owl2/utils";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

import {
    Plugin,
    Resource,
    computed,
    markRaw,
    onWillStart,
    proxy,
    signal,
    t,
    useConfig,
    useEffect,
    useListener,
    usePlugin,
    untrack,
} from "@odoo/owl";


/** Create a copy of a given object and check every property to transform them:
 * - if they are objects themselves, we recursively create virtual objects for them
 * - otherwise, they are primitives, so we create a signal for them to listen for changes.
 *
 * Using signal for the primitives reduces the amount of rendering done thanks to the computed field.
 * Since if the value of the computed doesn't change, a rendering of the component is not done.
 *
 * Some values of the lines, like the level, don't change very often between lines, while some do like the value in the cell of a line.
 * By using signal, we also know when the value rather than the presence of the value is needed.
 * For example, we need to give the value to the Ellipsis in the Cell, but the Cell itself doesn't need the value.
 * And using the signal, the Cell won't be rendered since only the Ellipsis will get the value (if done right ^^').
 *
 * P.S. This has been made to be used with the line object and not by any other weird object since we won't cover
 * all possible cases. Be aware of this if you intend to copy this to use it for something else.
 */
function createVirtualObject(object) {
    let ref = object;
    /** Since some keys are optional on the lines, such as account_status, by having the virtualObject as a proxy
     * we will listen for KEYCHANGES. This only triggers KEYCHANGES when adding the keys since we don't remove them
     * and simply set the result as undefined afterward to minimize the number of KEYCHANGES since they are the most
     * expensive operation to listen to.
     *
     * Since we never remove the keys, the virtualObject should all stabilize themselves after some time.
    */
    const isArray = object.constructor === Array;
    const virtualObject = proxy(isArray ? [] : {});
    const setTargets = isArray ? [] : {};
    const trackedKeys = [];
    const trackedKeySet = new Set();

    function watchKey(key) {
        const value = ref[key];
        const [childProxy, setTarget] = value !== null && typeof value === "object"  // null is considered an object
            ? createVirtualObject(value)
            : watchPrimitive(value, newValue => ref[key] = newValue);
        setTargets[key] = setTarget;
        virtualObject[key] = childProxy;
        trackedKeys.push(key);
        trackedKeySet.add(key);
    }

    for (const key of Object.keys(object)) {
        watchKey(key);
    }

    /** Update the existing keys, with the value of the deleted keys set to undefined (the key itself remains)
     * And add the new keys with their corresponding signal or virtual object.
     *
     * This will only trigger the updates on the key with changed values (similar to making a diff on the objects).
     * This check is done directly by the signal so we don't have to do it here.
     */
    function setTarget(target) {
        if (target === undefined || target === null) {
            target = isArray ? [] : {};
        }
        ref = target;

        /** Special case to handle lists.
         * Compared to an object, lists are made to be iterated using t-for (like the columns on the lines).
         *
         * This is only done with lists since removing a key (from an object or array) is a very expensive
         * operation since it triggers KEYCHANGES, which means every component (and their sub-component(s))
         * which listen to any key of the object will be targeted to be re-rendered.
         *
         * Also since this removes elements, it will trigger some Garbage Collection which can be very expensive.
         */
        if (isArray && target.length < virtualObject.length) {
            for (let i = target.length; i < trackedKeys.length; i++) {
                trackedKeySet.delete(trackedKeys[i]);
            }
            virtualObject.length = target.length;
            setTargets.length = target.length;
            trackedKeys.length = target.length;
        }

        for (let i = 0; i < trackedKeys.length; i++) {
            const key = trackedKeys[i];
            setTargets[key](target[key]);
        }

        for (const key of Object.keys(target)) {
            if (!trackedKeySet.has(key)) {
                watchKey(key);
            }
        }
    }

    return [virtualObject, setTarget];
}


function watchPrimitive(value, onSet) {
    const sig = signal(value);
    const comp = computed(sig, {
        set: newValue => {
            onSet(newValue);  // Update the real stored value.
            sig.set(newValue);
        },
    });
    return [comp, sig.set];
}


const VirtualGridType = t.object({
    firstRow: t.signal(t.number()),
    lastRow: t.signal(t.number()),
    firstColumn: t.signal(t.number()),
    lastColumn: t.signal(t.number()),
    setColumnWidths: t.function([t.array(t.number())]),
    setRowHeights: t.function([t.array(t.number())]),
});


export class AccountReportController extends Plugin {
    action = useConfig("action", t.object());

    orm = usePlugin(ORM);
    actionPlugin = usePlugin(ActionPlugin);
    dialog = usePlugin(DialogPlugin);
    ui = usePlugin(UIPlugin);

    chatterState = {
        model: signal(null),
        id: signal(null),
        lineId: signal(null), // To identify the line when editing / deleting a message
    };

    componentsMap = {};

    scrollableRef = useConfig("scrollableRef", t.function([], t.ref()));
    virtualGrids = useConfig("virtualGrids", t.signal(t.object({ left: VirtualGridType, right: VirtualGridType })));
    /** The virtualData contains:
     * - firstRow/lastRow: the index of the first and last row currently displayed.
     * - top/bottom: the height in pixel that the top/bottom padding should have.
     * - lines: the virtual lines that will be displayed (check createVirtualObject for what a virtual line is)
     * - numberOfVirtualLines: how many virtual lines to display. Since creating and destroying component is expensive,
     *      we use this to add `display: none` on the lines after this, allowing us to reduce the cost of rendering.
     */
    virtualData = {
        left: {
            firstRow: signal(0),
            lastRow: signal(0),
            top: signal(0),
            bottom: signal(0),
            lines: signal.Array([], { type: t.object() }),
            numberOfVirtualLines: signal(0),
        },
        right: {
            firstRow: signal(0),
            lastRow: signal(0),
            top: signal(0),
            bottom: signal(0),
            lines: signal.Array([], { type: t.object() }),
            numberOfVirtualLines: signal(0),
        },
    };
    /** lineHeights contains [top_padding, ...line_heights, bottom_padding] to have only one object to reduce Garbage Collection.
     * @type {{ left: number[], right: number[] }} */
    lineHeights = { left: [], right: [] };
    _invalidateVisibleLines = signal(false);
    linesOrder = signal(null);
    fakeLineRefs = new Resource({ name: "fakeLineRefs", validation: t.ref() });

    frameTaskQueue = [];
    frameTaskScheduled = false;

    classUpdateQueue = [];
    classUpdateScheduled = false;
    classUpdateLength = 0;

    accountStatuses = {};
    accountStatusFields = {
        status: {
            selection: [
                ['todo', 'To Review'],
                ['reviewed', 'Reviewed'],
                ['supervised', 'Supervised'],
                ['anomaly', 'Anomaly'],
            ],
            required: false,
        },
    };
    accountStatusModel = new RelationalModel(
        useEnv(),
        {
            config: {
                resModel: 'account.audit.account.status',
                fields: this.accountStatusFields,
                activeFields: this.accountStatusFields,
                openGroupsByDefault: true,
                isMonoRecord: true,
            },
            groupsLimit: Number.MAX_SAFE_INTEGER,
            limit: 1,
            countLimit: 1,
        },
        { orm: this.orm },
    );

    cachedFilterOptions = signal(null);  // the options used for the header.
    options = signal(null);
    data = signal(null);

    reportOptionsMap = {};
    reportInformationMap = {};
    lastOpenedSectionByReport = {};

    loadingCallNumberByCacheKey = new Proxy(
        {},
        {
            get(target, name) {
                return name in target ? target[name] : 0;
            },
            set(target, name, newValue) {
                target[name] = newValue;
                return true;
            },
        }
    );

    actionReportId = this.action.context.report_id;

    destroyed = false;

    setup() {
        super.setup();

        useEffect(() => {
            const invalidateVisibleLines = this._invalidateVisibleLines();
            this._computeVirtualData("left", invalidateVisibleLines, invalidateVisibleLines);
            this._computeVirtualData("right", invalidateVisibleLines, invalidateVisibleLines);
            untrack(() => this._invalidateVisibleLines.set(false));
        });
        // A window resize, can change the ratio of rem conversion, so the lineHeights ain't valid anymore.
        useListener(window, 'resize', () => this._invalidateVisibleLines.set(true));

        onWillStart(async () => {
            const isOpeningReport = !this.action?.keep_journal_groups_options;  // true when opening the report, except when coming from the breadcrumb
            const mainReportOptionsInfo = await this.loadReportOptions(this.actionReportId, false, this.action.params?.ignore_session, isOpeningReport);
            let mainReportOptions = await mainReportOptionsInfo.options;
            const cacheKey = this.getCacheKey(mainReportOptions['sections_source_id'], mainReportOptions['report_id']);

            // We need the options to be set and saved in order for the loading to work properly
            this.reportOptionsMap[cacheKey] = mainReportOptions;
            this.saveSessionOptions(mainReportOptions);
            mainReportOptions = proxy(mainReportOptions);
            this.options.set(mainReportOptions);
            this.cachedFilterOptions.set(mainReportOptions);

            this.reportLoadingPromise = this.displayReport(mainReportOptions['report_id']);
            this.preLoadClosedSections();

            if (!this.ui.isSmall()) {
                const chatterState = JSON.parse(window.sessionStorage.getItem(this.sessionChatterStateID()));
                this.chatterState.model.set(chatterState?.model);
                this.chatterState.id.set(chatterState?.id);
                this.chatterState.lineId.set(chatterState?.lineId);
            }
        });
    }

    getCacheKey(sectionsSourceId, reportId) {
        return `${sectionsSourceId}_${reportId}`;
    }

    async displayReport(reportId) {
        let {callNumber, options, cacheKey} = await this.loadReport(reportId);
        options = proxy(options);
        if (this.serverCallResultCanBeSetAsActive(callNumber, options, options, cacheKey))
            this.cachedFilterOptions.set(options);

        return this.loadInformationMap(options, cacheKey, callNumber);
    }

    serverCallResultCanBeSetAsActive(callNumber, callResult, options, cacheKey) {
        return callResult !== undefined
            && callNumber === this.loadingCallNumberByCacheKey[cacheKey]
            && (!Object.keys(this.lastOpenedSectionByReport).length || this.lastOpenedSectionByReport[options['selected_variant_id']] === options['selected_section_id']);
    }

    async loadInformationMap(options, cacheKey, callNumber) {
        this.loadingData = true;
        this.displayLoadingSymbolWhenTakingTooLong(options['report_id'] === this.options()['report_id']);

        const reportInformation = await this.reportInformationMap[cacheKey];
        if (!this.serverCallResultCanBeSetAsActive(callNumber, reportInformation, options, cacheKey)) return;
        this.loadingData = false;

        this.componentsMap = {};
        this.accountStatuses = {};
        this.options.set(options);
        this.saveSessionOptions(this.options());

        // If there is a specific order for lines in the options, we want to use it by default
        if (this.areLinesOrdered()) {
            this.linesOrder.set(await this.loadLinesOrder(reportInformation.lines));
        }
        else this.linesOrder.set(null);
        this.setLineVisibility(reportInformation.lines);
        this.refreshVisibleAnnotations(reportInformation.lines, reportInformation.annotations);

        this.data.set(proxy({ ...reportInformation, line: markRaw(reportInformation.lines) }));
        this._invalidateVisibleLines.set(true);  // So the useEffect know to reset the lineHeights and the fake line columns width

        // HACK: when changing report, the content gets emptied. So the browserequestAnimationFramer bring the window at the top. However,
        // the virtual grid doesn't receive a scroll event in the scrollableRef.
        requestAnimationFrame(() => {  // called before the scrollableRef is rendered
            requestAnimationFrame(() => {  // now it's rendered, we can simulate the scroll event to force the virtual grid to refresh.
                const el = this.scrollableRef();
                if (!el) return;
                const ev = new Event("scroll");
                Object.defineProperty(ev, "currentTarget", { value: el, configurable: true });
                el.dispatchEvent(ev);
            });
        });
    }

    async displayLoadingSymbolWhenTakingTooLong(longWaitBeforeLoadAnimation) {
        // Wait for 200 ms at least to prevent the loading animation from flickering if the report loads quickly.
        const waitingTime = longWaitBeforeLoadAnimation ? 500 : 200;
        await new Promise((resolve) => setTimeout(resolve, waitingTime));

        if (this.loadingData) {
            // Only invalidate the lines here, as if the report load quickly enough (thanks to the cache for example),
            // we will reuse the previous virtual line and components.
            this.data.set(null);
            this.virtualData.left.lines.set([]);
            this.virtualData.right.lines.set([]);
            this.virtualGrids().left.setRowHeights([]);
            this.virtualGrids().right.setRowHeights([]);
            this.fakeLineRefs.items().forEach(ref => this.fakeLineRefs.delete(ref));  // https://github.com/odoo/owl/issues/1981
        }
    }

    async reload(optionPath, newOptions) {
        const rootOptionKey = optionPath ? optionPath.split(".")[0] : "";

        /*
        When reloading the UI after setting an option filter, invalidate the cached options and data of all sections supporting this filter.
        This way, those sections will be reloaded (either synchronously when the user tries to access them or asynchronously via the preloading
        feature), and will then use the new filter value. This ensures the filters are always applied consistently to all sections.
        */
        for (const [cacheKey, cachedOptionsPromise] of Object.entries(this.reportOptionsMap)) {
            let cachedOptions = await cachedOptionsPromise;

            if (rootOptionKey === "" || cachedOptions.hasOwnProperty(rootOptionKey)) {
                delete this.reportOptionsMap[cacheKey];
                delete this.reportInformationMap[cacheKey];
            }
        }

        this.saveSessionOptions(newOptions); // The new options will be loaded from the session. Saving them now ensures the new filter is taken into account.
        await this.displayReport(newOptions['report_id']);
    }

    async preLoadClosedSections() {
        if (this.destroyed) return;

        let sectionLoaded = false;
        for (const section of this.options()['sections']) {
            // Preload the first non-loaded section we find amongst this report's sections.
            const cacheKey = this.getCacheKey(this.options()['sections_source_id'], section.id);
            if (section.id != this.options()['report_id'] && !this.reportInformationMap[cacheKey]) {
                const {cacheKey} = await this.loadReport(section.id, true);
                await this.reportInformationMap[cacheKey];

                sectionLoaded = true;
                // Stop iterating and schedule next call. We don't go on in the loop in case the cache is reset and we need to restart preloading.
                break;
            }
        }

        const nextCallDelay = (sectionLoaded) ? 100 : 1000;

        const self = this;
        setTimeout(() => self.preLoadClosedSections(), nextCallDelay);
    }

    async loadReport(reportId, preloading=false) {
        const reportOptionsInfo = await this.loadReportOptions(reportId, preloading, false); // This also sets the promise in the cache
        const options = await reportOptionsInfo.options;
        const reportToDisplayId = options['report_id']; // Might be different from reportId, in case the report to open uses sections

        const cacheKey = this.getCacheKey(options['sections_source_id'], reportToDisplayId);
        if (!this.reportInformationMap[cacheKey]) {
            this.asyncDataLoading = true;
            this.reportInformationMap[cacheKey] = this.orm
                .cache({
                    type: "disk",
                    update: "always",
                    maxAge: 90 * 60 * 1000,
                    callback: (result, hasChanged) => {
                        this.asyncDataLoading = false;
                        if (hasChanged) {
                            this.reportInformationMap[cacheKey] = Promise.resolve(result);
                            this.loadInformationMap(options, cacheKey, reportOptionsInfo.callNumber);
                        }
                    },
                })
                .call(
                    "account.report",
                    options.readonly_query
                        ? "get_report_information_readonly"
                        : "get_report_information",
                    [reportToDisplayId, options],
                    {
                        context: this.action.context,
                    },
                );
        }

        if (!preloading && options['sections'].length)
            this.lastOpenedSectionByReport[options['sections_source_id']] = options['selected_section_id'];

        return {cacheKey, options, callNumber: reportOptionsInfo.callNumber};
    }

    async loadReportOptions(reportId, preloading=false, ignore_session=false, isOpeningReport=false) {
        const loadOptions = (ignore_session || !this.hasSessionOptions()) ? (this.action.params?.options || {}) : this.sessionOptions();
        delete this.action.params?.ignore_session;
        const cacheKey = this.getCacheKey(loadOptions['sections_source_id'] || reportId, reportId);

        this.loadingCallNumberByCacheKey[cacheKey] += 1;
        const callNumber = this.loadingCallNumberByCacheKey[cacheKey];

        loadOptions["is_opening_report"] = isOpeningReport;

        let reportOptions = this.reportOptionsMap[cacheKey];
        if (!reportOptions) {
            // The options for this section are not loaded nor loading. Let's load them !

            if (preloading)
                loadOptions['selected_section_id'] = reportId;
            else {
                /* Reopen the last opened section by default (cannot be done through regular caching, because composite reports' options are not
                cached (since they always reroute). */
                if (this.lastOpenedSectionByReport[reportId])
                    loadOptions['selected_section_id'] = this.lastOpenedSectionByReport[reportId];
            }

            this.reportOptionsMap[cacheKey] = this.orm.call(
                "account.report",
                "get_options",
                [reportId, loadOptions],
                {
                    context: this.action.context,
                },
            );

            // Wait for the result, and check the report hasn't been rerouted to a section or variant; fix the cache if it has
            reportOptions = await this.reportOptionsMap[cacheKey];

            // In case of a reroute, also set the cached options into the reroute target's key
            const loadedOptionsCacheKey = this.getCacheKey(reportOptions['sections_source_id'], reportOptions['report_id']);
            if (loadedOptionsCacheKey !== cacheKey) {
                /* We delete the rerouting report from the cache, to avoid redoing this reroute when reloading the cached options, as it would mean
                route reports can never be opened directly if they open some variant by default.*/
                delete this.reportOptionsMap[cacheKey];
                this.reportOptionsMap[loadedOptionsCacheKey] = reportOptions;

                this.loadingCallNumberByCacheKey[loadedOptionsCacheKey] = 1;
                delete this.loadingCallNumberByCacheKey[cacheKey];
                return {callNumber: this.loadingCallNumberByCacheKey[loadedOptionsCacheKey], options: reportOptions};
            }
        }

        return {callNumber, options: reportOptions};
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Custom overrides
    // -----------------------------------------------------------------------------------------------------------------
    static registerCustomComponent(customComponent) {
        registry.category("account_reports.custom_components").add(customComponent.name, customComponent);
    }

    component(name) {
        const component = this.componentsMap[name];
        if (component !== undefined) return component;

        const customComponentName = this.options().custom_display_config.components?.[name];
        if (!customComponentName) {
            this.componentsMap[name] = registry.category("account_reports.default_components").get(name);
        }
        else {
            this.componentsMap[name] = registry.category("account_reports.custom_components").get(customComponentName);
        }
        return this.componentsMap[name];
    }

    template(name) {
        return this.options().custom_display_config.templates?.[name] || `account_reports.${ name }Customizable`;
    }

    //------------------------------------------------------------------------------------------------------------------
    // Generic data getters
    //------------------------------------------------------------------------------------------------------------------
    get buttons() {
        return this.cachedFilterOptions().buttons;
    }

    get caretOptions() {
        return this.data().caret_options;
    }

    get columnHeadersRenderData() {
        return this.data().column_headers_render_data;
    }

    get columnGroupsTotals() {
        return this.data().column_groups_totals;
    }

    get context() {
        return this.data().context;
    }

    get filters() {
        return this.cachedFilterOptions().filters;
    }

    get annotations() {
        return this.data().annotations;
    }

    get userGroups() {
        return this.options().user_groups;
    }

    get cachedUserGroups() {
        return this.cachedFilterOptions().user_groups;
    }

    get lines() {
        return this.data().lines;
    }

    get warnings() {
        return this.data().warnings;
    }

    get report() {
        return this.data().report;
    }

    //------------------------------------------------------------------------------------------------------------------
    // Generic data setters
    //------------------------------------------------------------------------------------------------------------------
    set annotations(value) {
        this.data().annotations = value;
    }

    set columnGroupsTotals(value) {
        this.data().column_groups_totals = value;
    }

    set lines(value) {
        this.data().lines = value;
        this.setLineVisibility(this.lines);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Helpers
    //------------------------------------------------------------------------------------------------------------------
    get needsColumnPercentComparison() {
        return this.options().column_percent_comparison === "growth"
          || this.options().column_percent_comparison === "report_line";
    }

    get needsAnalyticCoverageColumn() {
        return this.options().column_percent_comparison === "analytic_coverage";
    }

    get hasCustomSubheaders() {
        return this.columnHeadersRenderData.custom_subheaders.length > 0;
    }

    get hasDebugColumn() {
        return Boolean(this.options().show_debug_column);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Options
    //------------------------------------------------------------------------------------------------------------------
    async _updateOption(operationType, optionPath, optionValue=null, reloadUI=false) {
        const optionKeys = optionPath.split(".");

        let currentOptionKey;
        let option = this.cachedFilterOptions();

        while (optionKeys.length > 1) {
            currentOptionKey = optionKeys.shift();
            option = option[currentOptionKey];

            if (option === undefined)
                throw new Error(`Invalid option key in _updateOption(): ${ currentOptionKey } (${ optionPath })`);
        }

        switch (operationType) {
            case "update":
                option[optionKeys[0]] = optionValue;
                break;
            case "delete":
                option[optionKeys[0]] = undefined;
                break;
            case "toggle":
                option[optionKeys[0]] = !option[optionKeys[0]];
                break;
            default:
                throw new Error(`Invalid operation type in _updateOption(): ${ operationType }`);
        }

        if (reloadUI) {
            await this.reload(optionPath, this.cachedFilterOptions());
        }
    }

    async updateOption(optionPath, optionValue, reloadUI=false) {
        await this._updateOption('update', optionPath, optionValue, reloadUI);
    }

    async deleteOption(optionPath, reloadUI=false) {
        await this._updateOption('delete', optionPath, null, reloadUI);
    }

    async toggleOption(optionPath, reloadUI=false) {
        await this._updateOption('toggle', optionPath, null, reloadUI);
    }

    async switchToSection(reportId) {
        this.saveSessionOptions({...this.cachedFilterOptions(), 'selected_section_id': reportId});
        this.displayReport(reportId);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Session options
    //------------------------------------------------------------------------------------------------------------------
    sessionOptionsID() {
        /* Options are stored by action report (so, the report that was targetted by the original action triggering this flow).
        This allows a more intelligent reloading of the previous options during user navigation (especially concerning sections and variants;
        you expect your report to open by default the same section as last time you opened it in this http session).
        */
        const mainId = user.activeCompany.id;
        const otherIds = user.activeCompanies
            .filter((c) => c.id !== mainId)
            .map((c) => c.id)
            .sort((a, b) => a - b);

        return `account.report:${this.actionReportId}:${[mainId, ...otherIds].join(',')}`;
    }

    hasSessionOptions() {
        return Boolean(window.sessionStorage.getItem(this.sessionOptionsID()))
    }

    saveSessionOptions(options) {
        window.sessionStorage.setItem(this.sessionOptionsID(), JSON.stringify(options));
    }

    sessionOptions() {
        return JSON.parse(window.sessionStorage.getItem(this.sessionOptionsID()));
    }

    //------------------------------------------------------------------------------------------------------------------
    // Lines
    //------------------------------------------------------------------------------------------------------------------
    isLineAncestorOf(ancestorLineId, lineId) {
        return lineId.startsWith(`${ancestorLineId}|`);
    }

    isLineChildOf(childLineId, lineId) {
        return childLineId.startsWith(`${lineId}|`);
    }

    isLineRelatedTo(relatedLineId, lineId) {
        return this.isLineAncestorOf(relatedLineId, lineId) || this.isLineChildOf(relatedLineId, lineId);
    }

    isNextLineChild(index, lineId) {
        return index < this.lines.length && this.lines[index].id.startsWith(`${lineId}|`);
    }

    isNextLineDirectChild(index, lineId) {
        return index < this.lines.length && this.lines[index].parent_id === lineId;
    }

    isTotalLine(lineId) {
        return lineId.includes("|total~~");
    }

    isLoadMoreLine(lineId) {
        return lineId.includes("|load_more~~");
    }

    isLoadedLine(lineIndex) {
        const lineID = this.lines[lineIndex].id;
        const nextLineIndex = lineIndex + 1;
        const nextLineID = this.lines[nextLineIndex]?.id;

        return this.isNextLineChild(nextLineIndex, lineID) && !this.isTotalLine(nextLineID) && !this.isLoadMoreLine(nextLineID);
    }

    insertLinesAfter(insertIndex, newLines) {
        this.insertLines(insertIndex + 1, 0, newLines);
    }

    insertLines(lineIndex, deleteCount, newLines) {
        this.lines.splice(lineIndex, deleteCount, ...newLines);
        this.invalidateVisibleLines();
    }

    //------------------------------------------------------------------------------------------------------------------
    // Unfolded/Folded lines
    //------------------------------------------------------------------------------------------------------------------
    async unfoldLoadedLine(lineIndex) {
        const lineId = this.lines[lineIndex].id;
        let nextLineIndex = lineIndex + 1;

        while (this.isNextLineChild(nextLineIndex, lineId)) {
            if (this.isNextLineDirectChild(nextLineIndex, lineId)) {
                const nextLine = this.lines[nextLineIndex];
                nextLine.visible = true;
                if (!nextLine.unfoldable && this.isNextLineChild(nextLineIndex + 1, nextLine.id)) {
                    await this.unfoldLine(nextLineIndex);
                }
            }
            nextLineIndex += 1;
        }
        return nextLineIndex;
    }

    async unfoldNewLine(lineIndex) {
        const applyNewLines = (newLines) => {
            if (this.areLinesOrdered()) {
                this.updateLinesOrderIndexes(lineIndex, newLines, false);
            }

            this.insertLinesAfter(lineIndex, newLines);

            const totalIndex = lineIndex + newLines.length + 1;

            if (
                this.filters.show_totals
                && this.lines[totalIndex]
                && this.isTotalLine(this.lines[totalIndex].id)
            ) {
                this.lines[totalIndex].visible = true;
            }

            // Update options
            this.options().unfolded_lines.push(
                ...newLines.filter(line => line.unfolded).map(({ id }) => id)
            );

            this.saveSessionOptions(this.options());
            return totalIndex;
        };

        const options = await this.options();
        const newLines = await this.orm
            .cache({
                type: "disk",
                update: "always",
                maxAge: 90 * 60 * 1000,
                callback: (result, hasChanged) => {
                    if (hasChanged) {
                        // Remove previously cached lines.
                        let nextIndex = lineIndex + 1;
                        while (this.isNextLineChild(nextIndex, this.lines[lineIndex].id)) {
                            nextIndex += 1;
                        }
                        if (this.isTotalLine(this.lines[nextIndex - 1].id)) {
                            nextIndex -= 1;
                        }
                        const numberOfChildren = nextIndex - lineIndex - 1;
                        this.lines.splice(lineIndex + 1, numberOfChildren);

                        const lastLineIndex = applyNewLines(result);
                        const lines = this.lines.slice(lineIndex + 1, lastLineIndex);
                        this.loadAnnotations(lines);
                        this.setLineVisibility(lines);
                        this.invalidateVisibleLines();
                    }
                },
            })
            .call(
                "account.report",
                options.readonly_query ? "get_expanded_lines_readonly" : "get_expanded_lines",
                [
                    this.options()["report_id"],
                    this.options(),
                    this.lines[lineIndex].id,
                    this.lines[lineIndex].groupby,
                    this.lines[lineIndex].expand_function,
                    this.lines[lineIndex].horizontal_split_side,
                    this._retrieve_line_comparison_base_value(),
                ]
            );

        const totalIndex = applyNewLines(newLines);

        return totalIndex;
    }

    _retrieve_line_comparison_base_value() {
        if (this.options()?.comparison?.filter !== 'report_line') {
            return null;
        }

        const baseReportLineId = this.options().comparison.base_report_line.id;
        return this.lines.find((line) => line.columns[0].report_line_id === baseReportLineId).columns[0].no_format;
    }

    /**
     * When unfolding a line of a sorted report, we need to update the linesOrder array by adding the new lines,
     * which will require subsequent updates on the array.
     *
     * - lineOrderValue represents the line index before sorting the report.
     * @param {Integer} lineIndex: Index of the current line
     * @param {Array} newLines: Array of lines to be added
     * @param {Boolean} replaceLine: Useful for the splice of the linesOrder array in case we want to replace some line
     *                               example: With the load more, we want to replace the line with others
     **/
    updateLinesOrderIndexes(lineIndex, newLines, replaceLine) {
        let unfoldedLineIndex;
        // The offset is useful because in case we use 'replaceLineWith' we want to replace the line at index
        // unfoldedLineIndex with the new lines.
        const offset = replaceLine ? 0 : 1;
        const linesOrder = this.linesOrder();
        for (const [lineOrderIndex, lineOrderValue] of Object.entries(linesOrder)) {
            // Since we will have to add new lines into the linesOrder array, we have to update the index of the lines
            // having a bigger index than the one we will unfold.
            // deleteCount of 1 means that a line need to be replaced so the index need to be increase by 1 less than usual
            if (lineOrderValue > lineIndex) {
                linesOrder[lineOrderIndex] += newLines.length - replaceLine;
            }

            // The unfolded line is found, providing a reference for adding children in the 'linesOrder' array.
            if (lineOrderValue === lineIndex) {
                unfoldedLineIndex = parseInt(lineOrderIndex);
            }
        }
        const fullOffset = linesOrder[unfoldedLineIndex] + offset;
        const arrayOfNewIndex = range(fullOffset, newLines.length + fullOffset);
        linesOrder.splice(unfoldedLineIndex + offset, replaceLine, ...arrayOfNewIndex);
    }

    async unfoldLine(lineIndex) {
        const targetLine = this.lines[lineIndex];

        // Prevent concurrent unfold calls for the same line (e.g. from rapid clicks or a slow connection).
        if (targetLine.unfolding) return;
        targetLine.unfolding = true;

        try {
            let lastLineIndex = lineIndex + 1;
            const isLoadedLine = this.isLoadedLine(lineIndex);
            if (isLoadedLine) {
                lastLineIndex = await this.unfoldLoadedLine(lineIndex);
            } else if (targetLine.expand_function) {
                lastLineIndex = await this.unfoldNewLine(lineIndex);
            }

            lineIndex = this.lines.findIndex(line => line === targetLine);
            const lines = this.lines.slice(lineIndex + 1, lastLineIndex);

            if (!isLoadedLine && targetLine.expand_function)
                this.loadAnnotations(lines);

            this.setLineVisibility(lines);
            targetLine.unfolded = true;
            this.invalidateVisibleLines();

            // Update options
            if (!this.options().unfolded_lines.includes(targetLine.id))
                this.options().unfolded_lines.push(targetLine.id);

            this.saveSessionOptions(this.options());
        } finally {
            targetLine.unfolding = false;
        }
    }

    foldLine(lineIndex) {
        const targetLine = this.lines[lineIndex];

        const foldedLinesIDs = new Set([targetLine.id]);
        let nextLineIndex = lineIndex + 1;

        while (this.isNextLineChild(nextLineIndex, targetLine.id)) {
            this.lines[nextLineIndex].unfolded = false;
            this.lines[nextLineIndex].visible = false;

            foldedLinesIDs.add(this.lines[nextLineIndex].id);

            nextLineIndex += 1;
        }

        targetLine.unfolded = false;
        this.invalidateVisibleLines();

        // Update options
        this.options().unfolded_lines = this.options().unfolded_lines.filter(
            unfoldedLineID => !foldedLinesIDs.has(unfoldedLineID)
        );

        this.saveSessionOptions(this.options());
    }

    //------------------------------------------------------------------------------------------------------------------
    // Ordered lines
    //------------------------------------------------------------------------------------------------------------------
    linesCurrentOrderByColumn(columnIndex) {
        if (this.areLinesOrderedByColumn(columnIndex))
            return this.options().order_column.direction;
        return "default";
    }

    areLinesOrdered() {
        return this.linesOrder() !== null && this.options().order_column !== null;
    }

    areLinesOrderedByColumn(columnIndex) {
        return this.areLinesOrdered() && this.options().order_column.expression_label === this.options().columns[columnIndex].expression_label;
    }

    async sortLinesByColumnAsc(columnIndex) {
        this.options().order_column = {
            expression_label: this.options().columns[columnIndex].expression_label,
            direction: "ASC",
        };

        await this.sortLines();
        this.saveSessionOptions(this.options());
    }

    async sortLinesByColumnDesc(columnIndex) {
        this.options().order_column = {
            expression_label: this.options().columns[columnIndex].expression_label,
            direction: "DESC",
        };

        await this.sortLines();
        this.saveSessionOptions(this.options());
    }

    sortLinesByDefault() {
        this.options().order_column = undefined;
        this.linesOrder.set(null);

        this.saveSessionOptions(this.options());
    }

    async sortLines() {
        this.linesOrder.set(await this.loadLinesOrder(this.lines));
    }

    async loadLinesOrder(lines) {
        let columnIndex = undefined;
        for (const [i, column] of this.options().columns.entries()) {
            if (this.options().order_column.expression_label == column.expression_label) {
                columnIndex = i;
                break;
            }
        }

        if (columnIndex === undefined) {
            return lines.map((_, index) => index);
        }

        const minimalLineData = [];
        for (const line of lines) {
            minimalLineData.push([line.parent_id, line.id, line.columns[columnIndex].no_format]);
        }

        return await this.orm.call(
            "account.report",
            "sort_lines_from_client",
            [minimalLineData, this.options()],
            {
                context: this.action.context,
            },
        );
    }


    //------------------------------------------------------------------------------------------------------------------
    // Chatter
    //------------------------------------------------------------------------------------------------------------------
    sessionChatterStateID() {
        return this.sessionOptionsID() + user.activeCompany.id.toString() + ".chatter";
    }

    refreshVisibleAnnotations(lines = this.lines, annotations = this.annotations) {
        lines.forEach(line => { line.visible_annotations = annotations[line.id] && annotations[line.id].length > 0; });
    }

    async loadAnnotations(lines) {
        const line_dict_ids_by_record = {};

        for (const line of lines) {
            if (!line.chatter) continue;
            ((line_dict_ids_by_record[line.chatter.model] ??= {})[line.chatter.id] ??= []).push(line.id);
        }

        const new_annotations = await this.orm.call("account.report", "get_annotations_from_client", [
            this.action.context.report_id,
            this.options(),
            line_dict_ids_by_record,
        ]);
        Object.assign(this.annotations, new_annotations);
        this.refreshVisibleAnnotations(lines);
        this.invalidateVisibleLines();
    }

    addAnnotation(messageId, resModel, resId) {
        this.lines.forEach((line) => {
            if (line.chatter?.model === resModel && line.chatter?.id === resId) {
                this.annotations[line.id] = this.annotations[line.id] || [];
                this.annotations[line.id].push(messageId);
                line.visible_annotations = true;
            }
        });
        this.invalidateVisibleLines();
    }

    removeAnnotation(messageId) {
        this.lines.forEach(line => {
            this.annotations[line.id] = this.annotations[line.id]?.filter(mId => mId !== messageId) || [];
        });
        this.refreshVisibleAnnotations();
        this.invalidateVisibleLines();
    }

    async toggleLineChatter({ resModel, resId, lineId }) {
        if (
            this.chatterState.model() === resModel
            && this.chatterState.id() === resId
            && this.chatterState.lineId() === lineId
        ) {
            this.closeChatter();
        } else {
            this.chatterState.model.set(resModel);
            this.chatterState.id.set(resId);
            this.chatterState.lineId.set(lineId);
            window.sessionStorage.setItem(
                this.sessionChatterStateID(),
                JSON.stringify({
                    model: resModel,
                    id: resId,
                    lineId: lineId,
                })
            );
        }
    }

    closeChatter() {
        this.chatterState.model.set(null);
        this.chatterState.id.set(null);
        this.chatterState.lineId.set(null);
        window.sessionStorage.removeItem(this.sessionChatterStateID());
    }

    //------------------------------------------------------------------------------------------------------------------
    // Virtual Grid
    //------------------------------------------------------------------------------------------------------------------
    /** Force a refresh of the lines displayed to the end-user.
     * This should only need to be called when the stored lines or when any non-reactive dependency is added.
     *
     * @param {boolean} [animations=false] if the animations should play (by default no due to scrolling)
     */
    invalidateVisibleLines(animations = false) {
        this._computeVirtualData("left", true, false, animations);
        this._computeVirtualData('right', true, false, animations);
    }

    /** This function is the brain of the virtual grid.
     * Don't call `_computeVirtualData` directly, use `invalidateVisibleLines` instead.
     *
     * 1. Updates the line heights: it checks the lines currently rendered, takes their height, and saves it to have a better
     * idea of the real height of the line and don't need to randomly guess it.
     *
     * 2. Updates the "fake line". Similar to the lines, we don't know the width of the columns. Since we don't want the report
     * to change width when scrolling, we use this to keep memory (and rendering) of the largest width of each column.
     *
     * 3. Adds an 'is_rendering' class if not already present to prevent animations and transitions to prevent flickering since we
     * will be switching the value of everything. If a button switches very fast from true to false, its animation can be triggered and create a flickering.
     *
     * 4. Calculates the top and bottom padding so that the report has a scrollbar that closely matches the height of what it would
     * be if all the lines were rendered. This is done either for all lines if a invalidateLineHeights is passed (like when a major layout change
     * happens, e.g., if options/data change) or by calculating the difference with the last position (since O(n) on the stored line is expensive).
     *
     * 5. Updates the value of the virtual lines (the lines displayed) so they reflect the current position of the scrollbar.
     *  Also updates the value of the last line to display; since recreating components is expensive, we prefer to just hide them using this.
     *
     * This function's time complexity is around O(k + 2n) where k is the number of lines displayed and n is the difference between
     * the last start and the new row start. HOWEVER, when called with invalidateLineHeights=true, its complexity is O(m) where m is the stored
     * lines (which can get very big), so it's better to not over-call invalidateVisibleLines.
     * Also, using the horizontal_split doubles the number of lines/columns to display, doubling the time complexity.
     *
     * @param {'left' | 'right'} side The side of the virtual grid to update
     * @param {boolean} [invalidateLineHeights=false] If the line height cache should be invalidated
     * @param {boolean} [invalidateFakeLine=false] If the width of the column of the fake line should be reset
     * @param {boolean} [animations=false] If the animations should play (by default no due to scrolling)
     */
    _computeVirtualData(side, invalidateLineHeights = false, invalidateFakeLine = false, animations = false) {
        const virtualData = this.virtualData[side];
        // If the report isn't loaded then nothing to display. If not using horizontal split, the right virtual grid isn't used.
        if (this.data() === null || this.options() === null || (!this.options().horizontal_split && side === 'right')) {
            if (virtualData.lines().length > 0) {  // To not update the table for nothing if it was already empty.
                virtualData.lines.set([]);
            }
            virtualData.top.set(0);
            virtualData.bottom.set(0);
            return;
        }

        untrack(() => {
            this.updateLineHeights(side, invalidateLineHeights);
            this.updateFakeLine(side, invalidateFakeLine);
        });

        const virtualGrid = this.virtualGrids()[side];
        const firstRow = Math.max(0, virtualGrid.firstRow() - 1);  // To remove header and table padding
        const lastRow = Math.min(this.lines.length - 1, virtualGrid.lastRow() - 2); // To remove table padding

        if (!animations) {
            const scrollableRef = untrack(() => this.scrollableRef());
            this.scheduleFrameTask(() => { scrollableRef?.classList.add('is_rendering'); });
            clearTimeout(this.scrollRendingTimeout);
            this.scrollRendingTimeout = setTimeout(() => scrollableRef?.classList.remove('is_rendering'), 500);
        }

        const lineHeights = this.lineHeights[side];
        const areLinesOrdered = this.areLinesOrdered();
        const linesOrder = this.linesOrder();
        if (invalidateLineHeights) {
            virtualData.top.set(lineHeights.slice(1, firstRow + 1).reduce((acc, height) => acc + height, 0));
            virtualData.bottom.set(lineHeights.slice(lastRow + 2, lineHeights.length - 1).reduce((acc, height) => acc + height, 0));
        } else {
            const previousRowStart = untrack(() => virtualData.firstRow());
            const previousRowEnd = untrack(() => virtualData.lastRow());

            function sumLineHeights(startIndex, endIndex) {
                let totalHeight = 0;
                for (let i = startIndex; i <= endIndex; i++) {
                    const index = areLinesOrdered ? linesOrder[i] : i;
                    totalHeight += lineHeights[index + 1] || 0;
                }
                return totalHeight;
            };

            let top = untrack(() => virtualData.top());
            if (firstRow > previousRowStart)
                top += sumLineHeights(previousRowStart, firstRow - 1);
            else if (firstRow < previousRowStart)
                top -= sumLineHeights(firstRow, previousRowStart - 1);
            virtualData.top.set(Math.max(0, top));

            let bottom = untrack(() => virtualData.bottom());
            if (lastRow > previousRowEnd)
                bottom -= sumLineHeights(previousRowEnd + 1, lastRow);
            else if (lastRow < previousRowEnd)
                bottom += sumLineHeights(lastRow + 1, previousRowEnd);
            virtualData.bottom.set(Math.max(0, bottom));
        }

        let numberOfVirtualLines = 0;
        const virtualLines = untrack(() => virtualData.lines());
        const lines = this.data().lines;
        for (let i = firstRow; i <= lastRow; i++) {
            const index = areLinesOrdered ? linesOrder[i] : i;
            const line = lines[index];
            if (!lineHeights[index + 1]) continue;

            this.loadAuditStatus(line);
            if (virtualLines.length <= numberOfVirtualLines) {
                const [virtualLine, setTarget] = createVirtualObject(line);
                virtualLines.push({
                    lineIndex: signal(index),
                    line: virtualLine,
                    setTarget,
                });
            }
            else {
                const virtualLine = virtualLines[numberOfVirtualLines];
                virtualLine.setTarget(line);
                virtualLine.lineIndex.set(index);
            }
            numberOfVirtualLines++;
        }
        virtualData.numberOfVirtualLines.set(numberOfVirtualLines);
        virtualData.firstRow.set(firstRow);
        virtualData.lastRow.set(lastRow);
    }

    /** When invalidateLineHeights, refresh the height of all the lines based on the height of the rendered lines.
     * Afterward, update the top and bottom padding of the table and update the rowHeights for the virtual grid.
     *
     * @param {'left' | 'right'} side the side of the horizontal split
     * @param {boolean} invalidateLineHeights if the expensive changes should be made
     */
    updateLineHeights(side, invalidateLineHeights) {
        if (!invalidateLineHeights) return;

        // estimating a line height doesn't work due to Chrome rounding it to 1/64 and not Firefox (and more ...)
        // So we need to render one. This solution should work for 99% of cases since a fixed height is specified in the css.
        // if a custom line height is needed, a custom component is needed and getLineHeight needed to be defined on it to
        // return the approximate height the line should be (the closer to reality the better).
        const probeContainer = document.createElement('div');
        probeContainer.style.position = 'absolute';
        probeContainer.style.visibility = 'hidden';
        probeContainer.style.pointerEvents = 'none';
        probeContainer.innerHTML = `<div class="account_report"><table class="table"><tbody> <tr><td/></tr> </tbody></table></div>`;
        document.body.appendChild(probeContainer);
        const normalLineHeight = probeContainer.querySelector('tr').getBoundingClientRect().height || 0;
        document.body.removeChild(probeContainer);

        const lines = this.data().lines;
        const lineHeights = this.lineHeights[side];
        lineHeights.length = lines.length + 2;
        const lineComponent = this.component('AccountReportLine');
        for (let i = 0; i < lines.length; i++) {
            const height = lineComponent.getLineHeight(this, side, lines[i], normalLineHeight);
            lineHeights[i + 1] = height;
        }

        const scrollableRef = this.scrollableRef();
        const scrollableRect = scrollableRef?.querySelector('.o_account_report_scroll_content')?.getBoundingClientRect();
        const tableSelector = `table:nth-child(${side === 'left' ? 1 : 2})`;
        const contentRect = scrollableRef?.querySelector(`${tableSelector} tbody`)?.getBoundingClientRect();
        let bottomPadding = 0;
        if (scrollableRef) {
            bottomPadding = parseFloat(getComputedStyle(scrollableRef).paddingBottom) || 0;
        }

        lineHeights[0] = (contentRect?.top || 0) - (scrollableRect?.top || 0);
        lineHeights[lineHeights.length - 1] = Math.max(0, (
            (scrollableRect?.bottom || 0)
            - (contentRect?.bottom || 0)
            + bottomPadding
        ));

        this.virtualGrids()[side].setRowHeights(lineHeights);
    }

    /** We don't know the width of the columns until they are rendered.
     * Since we don't want to have the width of the columns grow and shrink when scrolling,
     * we use a "fake line" which will be used as a line with the largest known widths for each column.
     *
     * @param {'left' | 'right'} side The side of the horizontal split we want to update
     * @param {boolean} invalidateFakeLine If the columns width should be reset due to major change
     */
    updateFakeLine(side, invalidateFakeLine) {
        const fakeLine = this.fakeLineRefs.items().find(ref => ref.id === side);
        if (!fakeLine) return;  // Report wasn't rendered yet.

        const tableSelector = `table:nth-child(${side === 'left' ? 1 : 2})`;
        const tableTakes50PercentOrLess = () => (  // as a function so we don't uselessly calculate it when not needed
            this.scrollableRef()?.querySelector(tableSelector)?.getBoundingClientRect().width
            <= this.scrollableRef()?.getBoundingClientRect().width / 2
        );
        const prop = (this.options().horizontal_split && tableTakes50PercentOrLess()) ? 'width' : 'minWidth';

        const tds = fakeLine.querySelectorAll('td');
        if(invalidateFakeLine) {
            this.scheduleFrameTask(() => {
                for (let i = 0; i < tds.length; i++) {
                    if (tds[i].style[prop] !== 0) {
                        tds[i].style[prop] = 0;
                    }
                }
            });
        } else {
            const widths = Array.from(tds, td => `${td.getBoundingClientRect().width}px`);
            this.scheduleFrameTask(() => {
                for (let i = 0; i < tds.length; i++) {
                    if (tds[i].style[prop] !== widths[i]) {
                        tds[i].style[prop] = widths[i];
                    }
                }
            });
        }
    }

    loadAuditStatus(line) {
        if (!line.account_status || line.account_status.id in this.accountStatuses) return;

        // Cannot be stored on the line directly since the virtual line creates a watch on the line object recursively
        // and since the Record object contains recursion, it would create an infinite loop.
        this.accountStatuses[line.account_status.id] = untrack(() =>
            new this.accountStatusModel.constructor.Record(
                this.accountStatusModel,
                {
                    context: this.context,
                    activeFields: this.accountStatusFields,
                    fields: this.accountStatusFields,
                    resModel: 'account.audit.account.status',
                    resId: line.account_status.id,
                    resIds: [line.account_status.id],
                    isMonoRecord: true,
                    mode: 'readonly',
                },
                line.account_status,
                { manuallyAdded: !line.account_status.id },
            )
        );
    }

    /** Several unrelated spots in the report (scroll "is_rendering" class, fake line width probing, line/cell
     * class updates) each want to touch the DOM outside of Owl's render cycle on the next frame. Instead of every
     * one of them calling its own requestAnimationFrame (which the browser would still run back-to-back in the
     * same frame anyway), they register a task here so only a single requestAnimationFrame is scheduled per frame.
     *
     * @param {() => void} task
     */
    scheduleFrameTask(task) {
        this.frameTaskQueue.push(task);
        if (this.frameTaskScheduled) return;
        this.frameTaskScheduled = true;

        requestAnimationFrame(() => {
            this.frameTaskScheduled = false;
            const queue = this.frameTaskQueue;
            this.frameTaskQueue = [];
            for (const task of queue) task();
        });
    }

    /** Lines and cells need to add/remove some classes on their root element outside of Owl's render cycle
     * (to avoid triggering a re-render just for a class change). Since there can be hundreds of them, they are
     * queued here instead of each one registering its own frame task, and flushed in a single pass.
     *
     * @param {import("@odoo/owl").Signal<HTMLElement | null>} getRef function returning the element to update (evaluated at flush time, once the ref is set)
     * @param {string[]} prevClasses classes to remove
     * @param {string[]} nextClasses classes to add
     */
    scheduleClassUpdate(getRef, prevClasses, nextClasses) {
        const queue = this.classUpdateQueue;
        queue[this.classUpdateLength * 3] = getRef;
        queue[this.classUpdateLength * 3 + 1] = prevClasses;
        queue[this.classUpdateLength * 3 + 2] = nextClasses;
        this.classUpdateLength += 1;

        if (this.classUpdateScheduled) return;
        this.classUpdateScheduled = true;

        this.scheduleFrameTask(() => {
            this.classUpdateScheduled = false;

            for (let i = 0; i < this.classUpdateLength; i++) {
                const el = queue[i * 3]();
                if (!el) continue;

                const prevClasses = queue[i * 3 + 1];
                const nextClasses = queue[i * 3 + 2];
                if (prevClasses.length) el.classList.remove(...prevClasses);
                if (nextClasses.length) el.classList.add(...nextClasses);
            }
            this.classUpdateLength = 0;
        });
    }

    //------------------------------------------------------------------------------------------------------------------
    // Visibility
    //------------------------------------------------------------------------------------------------------------------

    /**
        Defines which lines should be visible in the provided list of lines (depending on what is folded).
    **/
    setLineVisibility(linesToAssign) {
        const needHidingChildren = new Set();

        linesToAssign.forEach((line) => {
            line.visible = !needHidingChildren.has(line.parent_id);

            if (!line.visible || (line.unfoldable &! line.unfolded))
                needHidingChildren.add(line.id);
        });

        // If the hide 0 lines is activated we will go through the lines to set the visibility.
        if (this.options().hide_0_lines) {
            this.hideZeroLines(linesToAssign);
        }
    }

    /**
     * Defines whether the line should be visible depending on its value and the ones of its children.
     * For parent lines, it's visible if there is at least one child with a value different from zero
     * or if a child is visible, indicating it's a parent line.
     * For leaf nodes, it's visible if the value is different from zero.
     *
     * By traversing the 'lines' array in reverse, we can set the visibility of the lines easily by keeping
     * a dict of visible lines for each parent.
     *
     * @param {Object[]} lines - The lines for which we want to determine visibility.
     */
    hideZeroLines(lines) {
        const hasVisibleChildren = new Set();
        const reversed_lines = [...lines].reverse()

        const number_figure_types = ['integer', 'float', 'monetary', 'percentage'];
        reversed_lines.forEach((line) => {
            const isZero = line.columns.every(column => !number_figure_types.includes(column.figure_type) || column.is_zero);

            // If the line has no visible children and all the columns are equals to zero then the line needs to be hidden
            if (!hasVisibleChildren.has(line.id) && isZero) {
                line.visible = false;
            }

            // If the line has a parent_id and is not hidden then we fill the set 'hasVisibleChildren'. Each parent
            // will have an array of his visible children
            if (line.parent_id && line.visible) {
                // This line allows the initialization of that list.
                hasVisibleChildren.add(line.parent_id);
            }
        });
    }

    //------------------------------------------------------------------------------------------------------------------
    // Server calls
    //------------------------------------------------------------------------------------------------------------------
    buttonAction(ev, button) {
        // Might be overidden to add specific functionality to button
        // For instance adding context to a call ...
        this.reportAction(ev, button.error_action || button.action, button.action_param, true);
    }

    async reportAction(ev, action, actionParam = null, callOnSectionsSource = false, actionContext=null, confirmationDialog=false) {
        // 'ev' might be 'undefined' if event is not triggered from a button/anchor
        ev?.preventDefault();
        ev?.stopPropagation();

        let actionOptions = this.cachedFilterOptions();
        if (callOnSectionsSource) {
            // When calling the sections source, we want to keep track of all unfolded lines of all sections
            const allUnfoldedLines =  this.cachedFilterOptions().sections.length ? [] : [...this.cachedFilterOptions().unfolded_lines];

            for (const sectionData of this.cachedFilterOptions()['sections']) {
                const cacheKey = this.getCacheKey(this.cachedFilterOptions().sections_source_id, sectionData.id);
                const sectionOptions = await this.reportOptionsMap[cacheKey];
                if (sectionOptions)
                    allUnfoldedLines.push(...sectionOptions.unfolded_lines);
            }

            actionOptions = {...this.cachedFilterOptions(), unfolded_lines: allUnfoldedLines};
        }

        if (confirmationDialog) {
            this.dialog.add(ConfirmationDialog, {
                body: _t("Are you sure you want to perform that action?"),
                confirm: async () =>
                    await this.dispatchReportAction(
                        actionOptions,
                        action,
                        actionParam,
                        callOnSectionsSource,
                        actionContext
                    ),
                cancel: () => {},
            });
        } else {
            await this.dispatchReportAction(
                actionOptions,
                action,
                actionParam,
                callOnSectionsSource,
                actionContext
            );
        }
    }

    async dispatchReportAction(
        actionOptions,
        action,
        actionParam,
        callOnSectionsSource,
        actionContext
    ) {
        const dispatchReportAction = await this.orm.call(
            "account.report",
            "dispatch_report_action",
            [
                this.cachedFilterOptions().report_id,
                actionOptions,
                action,
                actionParam,
                callOnSectionsSource,
            ],
            {
                context: Object.assign({}, this.action.context, actionContext),
            },
        );
        if (dispatchReportAction?.help) {
            dispatchReportAction.help = owl.markup(dispatchReportAction.help);
        }

        return dispatchReportAction ? this.actionPlugin.doAction(dispatchReportAction) : null;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Budget
    // -----------------------------------------------------------------------------------------------------------------

    async openBudget(budget) {
        this.actionPlugin.doAction({
            type: "ir.actions.act_window",
            res_model: "account.report.budget",
            res_id: budget.id,
            views: [[false, "form"]],
        });
    }
}
