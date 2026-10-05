import {
    Component,
    computed,
    markup,
    onMounted,
    onPatched,
    onWillUpdateProps,
    signal,
    t,
    useListener,
    useProps,
} from "@odoo/owl";
import { Domain } from "@web/core/domain";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_utils";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { useVirtualGrid } from "@web/core/virtual_grid_hook";
import { Field } from "@web/views/fields/field";
import { GridComponent } from "@web_grid/components/grid_component/grid_component";
import { GridScaleSelector } from "./grid_scale_selector";

export class GridRenderer extends Component {
    static components = {
        Field,
        GridComponent,
        GridScaleSelector,
    };

    static template = "web_grid.Renderer";

    static subTemplates = {
        header: "web_grid.Header",
        section: "web_grid.Section",
        row: "web_grid.Row",
        addLine: "web_grid.AddLine",
        footer: "web_grid.Footer",
        barChart: "web_grid.barChart",
        navigationButtons: "web_grid.NavigationButtons",
    };

    get subTemplates() {
        return this.constructor.subTemplates;
    }

    props = useProps({
        sections: t.array().optional([]),
        columns: t.array().optional([]),
        rows: t.array().optional([]),
        model: t.object().optional({}),
        options: t.object(),
        sectionField: t.object().optional(),
        rowFields: t.array(),
        measureField: t.object(),
        isEditable: t.boolean(),
        widgetPerFieldName: t.object(),
        openAction: t.object().optional(),
        contentRef: t.function(),
        createInline: t.boolean(),
        createRecord: t.function(),
        ranges: t.object().optional({}),
        state: t.object(),
        toggleWeekendVisibility: t.function(),
    });

    columnsGap = 1;
    rowsGap = 1;
    hoveredElement = null;
    isEditing = false;
    /** This property is used to avoid refocus on today whenever a cell value is updated. */
    shouldFocusOnToday = true;

    onMouseOver = useDebounced(this._onMouseOver.bind(this), 10);
    onMouseOut = useDebounced(this._onMouseOut.bind(this), 10);
    rootRef = signal.ref(HTMLDivElement);

    gridTemplateRows = computed(() => {
        let totalRows = 0;
        if (!this.props.options.hideColumnTotal) {
            totalRows += 1;
            if (this.props.options.hasBarChartTotal) {
                totalRows += 1;
            }
        }
        const addLineRows = this.props.createInline ? this.props.sections.length || 1 : 0;
        const rowsCount =
            this.props.rows.length - (this.props.model.sectionField ? 0 : 1) + addLineRows;

        // Row height must be hard-coded for the virtual hook to work properly.
        return `auto repeat(${rowsCount + totalRows}, ${this.rowHeight()}px)`;
    });
    gridTemplateColumns = computed(
        () =>
            `auto repeat(${this.props.columns.length}, ${
                this.props.columns.length > 7 ? "minmax(14ch, auto)" : "minmax(10ch, 1fr)"
            }) minmax(14ch, auto)`
    );
    measureLabel = computed(() => {
        const measureFieldName = this.props.model.measureFieldName;
        if (measureFieldName === "__count") {
            return _t("Total");
        }
        return (
            this.props.measureField.string || this.props.model.fieldsInfo[measureFieldName].string
        );
    });
    rowHeight = computed(() => {
        const { isSmall } = this.uiService;
        const baseHeight = isSmall ? 48 : 32;
        /*
         * On mobile devices, grouped by fields are stacked vertically.
         * By default, the base height accommodates up to 2 fields.
         * For each additional field beyond the first 2, we add 20px to maintain proper spacing.
         */
        const extraHeight = isSmall ? Math.max(0, this.props.model.rowFields.length - 2) * 20 : 0;
        return baseHeight + extraHeight;
    });
    virtualRows = computed(() =>
        this.props.rows.slice(this.virtualGrid.firstRow(), this.virtualGrid.lastRow() + 1)
    );

    setup() {
        this.actionService = useService("action");
        this.uiService = useService("ui");

        // Needs to be declared here because it depends on UI service
        this.virtualGrid = useVirtualGrid({
            scrollableRef: this.props.contentRef,
            rowHeights: this.props.rows.map((row) => this.getItemHeight(row, this.props)),
            initialScroll: { top: 60 },
        });

        const { fieldsInfo, measureFieldName } = this.props.model;
        const fieldInfo = fieldsInfo[measureFieldName];
        const measureFieldWidget = this.props.widgetPerFieldName[measureFieldName];
        const widgetName = measureFieldWidget || fieldInfo.type;
        this.gridCell = registry.category("grid_components").get(widgetName);

        const commonCellProps = {
            component: this.gridCell.component,
            fieldInfo,
            isMeasure: true,
            name: measureFieldName,
            readonly: !this.props.isEditable,
            type: widgetName,
            getCell: this.getCell.bind(this),
            onEdit: this.onEditCell.bind(this),
            openRecords: this.openRecords.bind(this),
        };
        /** props for hovered cell */
        this.hoveredCellProps = {
            ...commonCellProps,
            cell: signal.ref(),
            editMode: false,
            readonly: !this.props.isEditable,
        };
        /** props for cell in edit mode */
        this.editCellProps = {
            ...commonCellProps,
            cell: signal.ref(),
            editMode: true,
            readonly: !this.props.isEditable,
            onKeyDown: this.onCellKeydown.bind(this),
        };

        onWillUpdateProps(this.onWillUpdateProps);

        onMounted(this._focusOnToday);
        onPatched(this._focusOnToday);

        useListener(window, "click", this.onClick.bind(this));
        useListener(window, "keydown", this.onKeyDown.bind(this));
    }

    getCell(rowId, columnId) {
        return this.props.model.data.rows[rowId]?.cells[columnId];
    }

    getItemHeight(item, props) {
        if (item.isSection && item.isFake) {
            return 0;
        }
        let height = this.rowHeight();
        if (props.createInline && !item.isSection && item.section.lastRow.id === item.id) {
            height *= 2; // to include the Add a line row
        }
        return height;
    }

    getRowPosition(row, isCreateInlineRow = false) {
        const rowIndex = row ? this.props.rows.findIndex((r) => r.id === row.id) : 0;
        const section = row && row.getSection();
        const sectionDisplayed = Boolean(
            section && (section.value || this.props.sections.length > 1)
        );
        let rowPosition = this.rowsGap + rowIndex + 1 + (sectionDisplayed ? section.sectionId : 0);
        if (isCreateInlineRow) {
            rowPosition += 1;
        }
        if (!sectionDisplayed) {
            rowPosition -= 1;
        }
        return rowPosition;
    }

    getTotalRowPosition() {
        let sectionIndex = 0;
        if (this.props.model.sectionField && this.props.sections.length) {
            if (this.props.sections.length > 1 || this.props.sections[0].value) {
                sectionIndex = this.props.sections.length;
            }
        }
        return (
            (this.props.rows.length || 1) +
            sectionIndex +
            (this.props.createInline ? 1 : 0) +
            this.rowsGap
        );
    }

    onWillUpdateProps(nextProps) {
        this.virtualGrid.setRowHeights(
            nextProps.rows.map((row) => this.getItemHeight(row, nextProps))
        );
    }

    formatValue(value) {
        return this.gridCell.formatter(value);
    }

    getDisplayAddLine(row) {
        return this.props.createInline && row.id === row.section.lastRow.id;
    }

    getCellColorClass(column, section) {
        return "text-900";
    }

    getSectionColumnsClasses(column, row) {
        const isToday = column.isToday;
        return {
            "bg-info bg-opacity-50": isToday,
            "bg-200": !isToday,
            "bg-opacity-75":
                this.getUnavailableClass(column) === "o_grid_unavailable" &&
                row.cells[column.id].value === 0,
        };
    }

    getSectionCellsClasses(column, row) {
        return {
            "opacity-25":
                row.cells[column.id].value === 0 &&
                this.getUnavailableClass(column, row) === "o_grid_unavailable",
        };
    }

    isTextDanger() {
        return false;
    }

    getTextColorClasses(column, row, isEven) {
        const value = row.cells[column.id].value;
        const isTextDanger = this.isTextDanger(row, column);
        return {
            "text-900": !isEven && value >= 0 && !isTextDanger,
            "text-danger": value < 0 || isTextDanger,
        };
    }

    getCellsClasses(column, row, section, isEven) {
        return {
            ...this.getTextColorClasses(column, row, isEven),
            o_grid_cell_today: column.isToday,
            "fst-italic": row.isAdditionalRow,
        };
    }

    /**
     * @param {GridSection | GridRow} section
     * @param {number} grandTotal
     */
    _getTotalCellBgColor(section, grandTotal = 0) {
        return "text-bg-800";
    }

    getSectionTotalRowClass(section, grandTotal) {
        return {
            [this._getTotalCellBgColor(section, grandTotal)]: true,
            "text-opacity-25": grandTotal === 0,
            "bg-view": true,
        };
    }

    getSectionTotalTooltip(section, grandTotal) {
        return "";
    }

    getColumnTotalClassNames(column) {
        return {
            "text-danger":
                this.getUnavailableClass(column) == "o_grid_unavailable" && column.grandTotal > 0,
        };
    }

    getColumnBarChartHeightStyle(column) {
        let heightPercentage = 0;
        if (this.props.model.maxColumnsTotal !== 0) {
            heightPercentage = (column.grandTotal / this.props.model.maxColumnsTotal) * 100;
        }
        return `height: ${heightPercentage}%; bottom: 0;`;
    }

    getFooterTotalCellClasses(grandTotal) {
        if (grandTotal < 0) {
            return "border-danger bg-danger-subtle text-danger";
        }

        return "bg-100";
    }

    getUnavailableClass(column, section = undefined) {
        return "";
    }

    getFieldAdditionalProps(fieldName) {
        return {
            name: fieldName,
            type:
                this.props.widgetPerFieldName[fieldName] ||
                this.props.model.fieldsInfo[fieldName].type,
        };
    }

    getCellsTextClasses(column, row) {
        return {
            "text-900 text-opacity-25": row.cells[column.id].value === 0,
        };
    }

    getTotalCellsTextClasses(row, grandTotal) {
        return {
            "fst-italic": row.isAdditionalRow,
            "bg-view": grandTotal >= 0,
            "bg-danger text-bg-danger": grandTotal < 0,
            "text-opacity-50": grandTotal === 0,
        };
    }

    onCreateInlineClick(section) {
        const context = {
            ...(section?.context || {}),
        };
        const title = _t("Add a Line");
        this.props.createRecord({ context, title });
    }

    _focusOnToday() {
        if (!this.shouldFocusOnToday) {
            return;
        }
        this.shouldFocusOnToday = false;
        const { navigationInfo, columnFieldIsDate } = this.props.model;
        const { isSmall } = this.uiService;
        if (isSmall || !columnFieldIsDate || navigationInfo.range.name != "month") {
            return;
        }
        const rootEl = this.rootRef();
        const todayEl = rootEl.querySelector(
            "div.o_grid_column_title:has(.o_grid_cell_overlay_today)"
        );
        if (todayEl) {
            rootEl.parentElement.scrollLeft =
                todayEl.offsetLeft - rootEl.offsetWidth / 2 + todayEl.offsetWidth / 2;
        }
    }

    _onMouseOver(ev) {
        if (this.hoveredElement || ev.fromElement?.classList.contains("dropdown-item")) {
            // As mouseout is call prior to mouseover, if hoveredElement is set this means
            // that we haven't left it. So it's a mouseover inside it.
            return;
        }
        const highlightableElement = ev.target.closest(".o_grid_highlightable");
        if (!highlightableElement) {
            // We are not in an element that should trigger a highlight.
            return;
        }
        const { column, gridRow, gridColumn, row } = highlightableElement.dataset;
        const isCellInColumnTotalHighlighted =
            highlightableElement.classList.contains("o_grid_row_total");
        const elementsToHighlight = this.rootRef().querySelectorAll(
            `.o_grid_highlightable[data-grid-row="${gridRow}"]:not(.o_grid_add_line):not(.o_grid_column_title), .o_grid_highlightable[data-grid-column="${gridColumn}"]:not(.o_grid_section_title):not(.o_grid_row_title${
                isCellInColumnTotalHighlighted ? ",.o_grid_row_total" : ""
            })`
        );
        for (const node of elementsToHighlight) {
            if (node.classList.contains("o_grid_bar_chart_container")) {
                node.classList.add("o_grid_highlighted");
            }
            if (node.dataset.gridRow === gridRow) {
                node.classList.add("o_grid_highlighted");
                if (node.dataset.gridColumn === gridColumn) {
                    node.classList.add("o_grid_cell_highlighted");
                } else {
                    node.classList.add("o_grid_row_highlighted");
                }
            }
        }
        this.hoveredElement = highlightableElement;
        const cell = this.editCellProps.cell();
        if (
            row &&
            column &&
            !(cell && cell.dataset.row === row && cell.dataset.column === column)
        ) {
            this.hoveredCellProps.cell.set(highlightableElement);
        }
    }

    /**
     * Mouse out handler
     *
     * @param {MouseEvent} ev
     */
    _onMouseOut(ev) {
        if (!this.hoveredElement) {
            // If hoveredElement is not set this means were not in a o_grid_highlightable. So ignore it.
            return;
        }
        /** @type {HTMLElement | null} */
        let relatedTarget = ev.relatedTarget;
        const gridCell = relatedTarget?.closest(".o_grid_cell");
        if (
            gridCell &&
            gridCell.dataset.gridRow === this.hoveredElement.dataset.gridRow &&
            gridCell.dataset.gridColumn === this.hoveredElement.dataset.gridColumn &&
            gridCell !== this.editCellProps.cell()
        ) {
            return;
        }
        while (relatedTarget) {
            // Go up the parent chain
            if (relatedTarget === this.hoveredElement) {
                // Check that we are still inside hoveredConnector.
                // If so it means it is a transition between child elements so ignore it.
                return;
            }
            relatedTarget = relatedTarget.parentElement;
        }
        const { gridRow, gridColumn } = this.hoveredElement.dataset;
        const elementsHighlighted = this.rootRef().querySelectorAll(
            `.o_grid_highlightable[data-grid-row="${gridRow}"], .o_grid_highlightable[data-grid-column="${gridColumn}"]`
        );
        for (const node of elementsHighlighted) {
            node.classList.remove(
                "o_grid_highlighted",
                "o_grid_row_highlighted",
                "o_grid_cell_highlighted"
            );
        }
        this.hoveredElement = null;
        if (this.hoveredCellProps.cell()) {
            this.hoveredCellProps
                .cell()
                .querySelector(".o_grid_cell_readonly")
                .classList.remove("d-none");
            this.hoveredCellProps.cell.set(null);
        }
    }

    onEditCell(value) {
        if (this.editCellProps.cell()) {
            this.editCellProps
                .cell()
                .querySelector(".o_grid_cell_readonly")
                .classList.remove("d-none");
        }
        if (value) {
            this.editCellProps.cell.set(this.hoveredCellProps.cell());
            this.hoveredCellProps.cell.set(null);
        } else {
            this.editCellProps.cell.set(null);
        }
    }

    _onKeyDown(ev) {
        const hotkey = getActiveHotkey(ev);
        if (hotkey === "escape" && this.editCellProps.cell()) {
            this.onEditCell(false);
        }
    }

    /**
     * Handle click on any element in the grid
     *
     * @param {MouseEvent} ev
     */
    onClick(ev) {
        if (
            !this.editCellProps.cell() ||
            ev.target.closest(".o_grid_highlighted") ||
            ev.target.closest(".o_grid_cell")
        ) {
            return;
        }
        this.onEditCell(false);
    }

    onKeyDown(ev) {
        this._onKeyDown(ev);
    }

    /**
     * Handle the click on a cell in mobile
     *
     * @param {MouseEvent} ev
     */
    onCellClick(ev) {
        ev.stopPropagation();
        const cell = ev.target.closest(".o_grid_highlightable");
        const { row, column } = cell.dataset;
        if (row && column) {
            if (this.editCellProps.cell()) {
                this.editCellProps
                    .cell()
                    .querySelector(".o_grid_cell_readonly")
                    .classList.remove("d-none");
            }
            this.editCellProps.cell.set(cell);
        }
    }

    /**
     * Handle keydown when cell is edited in the grid view.
     *
     * @param {KeyboardEvent} ev
     * @param {import("./grid_model").GridCell | null} cell
     */
    onCellKeydown(ev, cell) {
        const hotkey = getActiveHotkey(ev);
        if (!this.rootRef() || !cell || !["tab", "shift+tab", "enter"].includes(hotkey)) {
            this._onKeyDown(ev);
            return;
        }
        // Purpose: prevent browser defaults
        ev.preventDefault();
        // Purpose: stop other window keydown listeners (e.g. home menu)
        ev.stopImmediatePropagation();
        let rowId = cell.row.id;
        let columnId = cell.column.id;
        const columnIds = this.props.columns.map((c) => c.id);
        const rowIds = [];
        for (const item of this.props.rows) {
            if (!item.isSection) {
                rowIds.push(item.id);
            }
        }
        let columnIndex = columnIds.indexOf(columnId);
        let rowIndex = rowIds.indexOf(rowId);
        if (hotkey === "tab") {
            columnIndex += 1;
            rowIndex += 1;
            if (columnIndex < columnIds.length) {
                columnId = columnIds[columnIndex];
            } else {
                columnId = columnIds[0];
                if (rowIndex < rowIds.length) {
                    rowId = rowIds[rowIndex];
                } else {
                    rowId = rowIds[0];
                }
            }
        } else if (hotkey === "shift+tab") {
            columnIndex -= 1;
            rowIndex -= 1;
            if (columnIndex >= 0) {
                columnId = columnIds[columnIndex];
            } else {
                columnId = columnIds[columnIds.length - 1];
                if (rowIndex >= 0) {
                    rowId = rowIds[rowIndex];
                } else {
                    rowId = rowIds[rowIds.length - 1];
                }
            }
        } else if (hotkey === "enter") {
            rowIndex += 1;
            if (rowIndex >= rowIds.length) {
                columnIndex = (columnIndex + 1) % columnIds.length;
                columnId = columnIds[columnIndex];
            }
            rowIndex = rowIndex % rowIds.length;
            rowId = rowIds[rowIndex];
        }
        this.onEditCell(false);
        this.hoveredCellProps.cell.set(
            this.rootRef().querySelector(
                `.o_grid_highlightable[data-row="${rowId}"][data-column="${columnId}"]`
            )
        );
        this.onEditCell(true);
    }

    async openRecords(actionTitle, domain, context) {
        const resModel = this.props.model.resModel;
        if (this.props.openAction) {
            const resIds = await this.props.model.orm.search(resModel, domain);
            this.actionService.doActionButton({
                ...this.props.openAction,
                resModel,
                resIds,
                context,
            });
        } else {
            // retrieve form and list view ids from the action
            const { views = [] } = this.env.config;
            const viewTypes = this.uiService.isSmall ? ["kanban", "form"] : ["list", "form"];
            const openRecordsViews = viewTypes.map((viewType) => {
                const view = views.find((view) => view[1] === viewType);
                return [view ? view[0] : false, viewType];
            });
            this.actionService.doAction({
                type: "ir.actions.act_window",
                name: actionTitle,
                res_model: resModel,
                views: openRecordsViews,
                domain,
                context,
                help: this._getNoContentHelper(),
            });
        }
    }

    /** Return grid cell action helper when no records are found. */
    _getNoContentHelper() {
        const noActivitiesFound = _t("No activities found");
        return markup`<p class='o_view_nocontent_smiling_face'>${noActivitiesFound}</p>`;
    }

    onMagnifierGlassClick(section, column) {
        const title = `${section.title} (${column.title})`;
        const domain = Domain.and([section.domain, column.domain]).toList();
        this.openRecords(title, domain, section.context);
    }

    async onRangeClick(name) {
        await this.props.model.setRange(name);
        this.props.state.activeRangeName = name;
        this.shouldFocusOnToday = true;
    }

    async onTodayButtonClick() {
        await this.props.model.setTodayAnchor();
        this.shouldFocusOnToday = true;
    }

    async onPreviousButtonClick() {
        await this.props.model.moveAnchor("backward");
        this.shouldFocusOnToday = true;
    }

    async onNextButtonClick() {
        await this.props.model.moveAnchor("forward");
        this.shouldFocusOnToday = true;
    }
}
