import { Domain } from "@web/core/domain";
import { EditListSortingSection } from "./edit_list_sorting_section/edit_list_sorting_section";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { asyncComputed, Component, onWillStart, proxy, usePlugin, t, useProps } from "@odoo/owl";
import { getListHighlights } from "../list_highlight_helpers";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

import { hooks, components, helpers } from "@odoo/o-spreadsheet";
import { SidePanelDomain } from "../../components/side_panel_domain/side_panel_domain";
import { RelatedFiltersSection } from "../../global_filters/components/related_filters_section/related_filters_section";
import { ListDimensions } from "./list_dimensions/list_dimensions";
import { SidepanelModelFieldSelector } from "../../components/sidepanel_model_field_selector/sidepanel_model_field_selector";
import { SEARCH_COUNT_LIMIT } from "@spreadsheet/list/list_data_source";

const { useHighlights } = hooks;
const { ValidationMessages, CogWheelMenu, Section, TextInput, Checkbox } = components;
const { getUniqueText, replaceSymbolInFormula } = helpers;

export class ListDetailsSidePanel extends Component {
    static template = "spreadsheet_edition.ListDetailsSidePanel";
    static components = {
        ValidationMessages,
        CogWheelMenu,
        Section,
        SidePanelDomain,
        TextInput,
        EditListSortingSection,
        RelatedFiltersSection,
        SidepanelModelFieldSelector,
        ListDimensions,
        Checkbox,
    };

    props = useProps({
        onCloseSidePanel: t.function(),
        listId: t.string(),
    });

    debugMode = usePlugin(DebugModePlugin);

    state = proxy({
        fullRecordCount: false,
    });

    recordsCount = asyncComputed(() => this.fetchRecordsCount(this.state.fullRecordCount));

    _dimensions = [];

    setup() {
        this.getters = this.env.model.getters;
        this.notification = useService("notification");
        this.fieldService = useService("field");
        const loadData = async (listId) => {
            const dataSource = await this.env.model.getters.getAsyncListDataSource(listId);
            this.isModelValid = dataSource.isModelValid();
            if (this.isModelValid) {
                this.modelDisplayName = await dataSource.getModelLabel();
                // Store the fields here because the data source can be reset when updating the list.
                // Forcing a reload with onWillUpdateProps would introduce flickering
                // and the fields never change anyway.
                this.listFields = dataSource.getFields();
            }
        };
        onWillStart(async () => {
            // it's assumed `this.props.listId` never changes (t-key is required when using this component)
            await loadData(this.props.listId);
        });
        useHighlights(this);
    }

    onTranslateCustomHeadersChanged(value) {
        this.udpateListDefinition({ translateHeaders: value });
    }

    get cogWheelMenuItems() {
        return [
            {
                name: "Duplicate",
                icon: "o-spreadsheet-Icon.COPY",
                execute: () => this.duplicateList(),
            },
            {
                name: "Delete",
                icon: "o-spreadsheet-Icon.TRASH",
                execute: () => this.deleteList(),
            },
        ];
    }

    async fetchRecordsCount(fullCount) {
        return await this.env.model.getters
            .getListDataSource(this.props.listId)
            .getRecordsCount({ fullCount });
    }

    get canFetchMoreRecords() {
        return !this.state.fullRecordCount && this.recordsCount() >= SEARCH_COUNT_LIMIT;
    }

    async fetchMoreRecords() {
        if (this.canFetchMoreRecords) {
            await this.recordsCount.currentPromise();
            this.state.fullRecordCount = true;
        }
    }

    get recordsCountText() {
        if (this.canFetchMoreRecords) {
            return _t("%(record_count)s+ records", {
                record_count: this.recordsCount(),
            });
        }
        return _t("%(record_count)s records", { record_count: this.recordsCount() });
    }

    get listDefinition() {
        const listId = this.props.listId;
        const def = this.getters.getListDefinition(listId);
        return {
            model: def.model,
            modelDisplayName: this.modelDisplayName,
            domain: new Domain(def.domain).toString(),
            orderBy: def.orderBy,
            translateHeaders: def.translateHeaders,
        };
    }

    getDimensions() {
        const listId = this.props.listId;
        const def = this.getters.getListDefinition(listId);
        const ds = this.env.model.getters.getListDataSource(listId);
        if (ds.isReady()) {
            // on slow networks, this will prevent drastic change of display
            // until the datasource is updated and the field paths are fetched.
            this._dimensions = def.columns.map((col) => {
                if (col.computedBy) {
                    return {
                        name: col.name,
                        string: col.string || col.name,
                        computedBy: col.computedBy,
                        isValid: true,
                        hidden: col.hidden,
                    };
                } else {
                    const field = ds.getFieldFromFieldPath(col.name);
                    return {
                        name: col.name,
                        fieldString: field?.fullString || col.name,
                        string: col.string || field?.string || col.name,
                        isValid: !!field,
                        hidden: col.hidden,
                    };
                }
            });
        }
        return this._dimensions;
    }

    get invalidListModel() {
        const model = this.env.model.getters.getListDefinition(this.props.listId).model;
        return _t(
            "The model (%(model)s) of this list is not valid (it may have been renamed/deleted). Please re-insert a new list.",
            {
                model,
            }
        );
    }

    getLastUpdate() {
        const lastUpdate = this.env.model.getters.getListDataSource(this.props.listId).lastUpdate;
        if (lastUpdate) {
            return new Date(lastUpdate).toLocaleTimeString();
        }
        return _t("never");
    }

    onNameChanged(name) {
        this.env.model.dispatch("RENAME_ODOO_LIST", {
            listId: this.props.listId,
            name,
        });
    }

    onDomainUpdate(domain) {
        this.state.fullRecordCount = false;
        this.udpateListDefinition({ domain });
    }

    /**
     * @param {{name: string, asc: boolean}[]} orderBy
     */
    onUpdateSorting(orderBy) {
        this.udpateListDefinition({ orderBy });
    }

    duplicateList() {
        const newListId = this.env.model.getters.getNextListId();
        const result = this.env.model.dispatch("DUPLICATE_ODOO_LIST_IN_NEW_SHEET", {
            listId: this.props.listId,
            newListId,
            linesNumber: 80,
        });

        const msg = result.isSuccessful ? _t("List duplicated.") : _t("List duplication failed");
        const type = result.isSuccessful ? "success" : "danger";
        this.notification.add(msg, { sticky: false, type });

        if (result.isSuccessful) {
            this.env.openSidePanel("LIST_PROPERTIES_PANEL", {
                listId: newListId,
            });
        }
    }

    deleteList() {
        this.env.askConfirmation(_t("Are you sure you want to delete this list?"), () => {
            this.env.model.dispatch("REMOVE_ODOO_LIST", {
                listId: this.props.listId,
            });
            this.props.onCloseSidePanel();
        });
    }

    get unusedListWarning() {
        return _t("This list is not used");
    }

    get highlights() {
        return getListHighlights(this.env, this.props.listId);
    }

    onRemoveDimension(column) {
        const columns = this.getters
            .getListDefinition(this.props.listId)
            .columns.filter((col) => col.name !== column.name);
        this.udpateListDefinition({ columns });
    }

    calculatedColumnName(columnNames, string) {
        return getUniqueText(string, columnNames, {
            compute: (text, increment) => `${text}:${increment + 1}`,
        });
    }

    onRenameDimension(column, newString) {
        const columns = [...this.getters.getListDefinition(this.props.listId).columns];
        const updatedColumnIndex = columns.findIndex((col) => col.name === column.name);
        if (!newString) {
            if (columns[updatedColumnIndex].computedBy) {
                return;
            } else {
                newString = this.getColumnFieldDisplayName(column);
            }
        }
        if (columns[updatedColumnIndex].string === newString) {
            return;
        }
        const oldColumn = columns[updatedColumnIndex];
        if (columns[updatedColumnIndex].computedBy) {
            const newName = this.calculatedColumnName(
                columns.map((col) => col.name),
                newString
            );
            columns[updatedColumnIndex] = {
                ...columns[updatedColumnIndex],
                string: newString,
                name: newName,
            };
        } else {
            if (newString) {
                columns[updatedColumnIndex] = {
                    ...columns[updatedColumnIndex],
                    string: newString,
                };
                this.udpateListDefinition({ columns });
            }
            return;
        }
        const newColumn = columns[updatedColumnIndex];
        for (let colIndex = 0; colIndex < columns.length; colIndex++) {
            const col = columns[colIndex];
            if (!col.computedBy) {
                continue;
            }
            const newFormula = replaceSymbolInFormula(
                col.computedBy.formula,
                oldColumn.name,
                newColumn.name
            );
            if (newFormula !== col.computedBy.formula) {
                columns[colIndex] = {
                    ...col,
                    computedBy: {
                        formula: newFormula,
                        sheetId: col.computedBy.sheetId,
                    },
                };
            }
        }
        this.udpateListDefinition({ columns });
    }

    async addDimension(columnName, { fieldDef }) {
        const columns = [...this.getters.getListDefinition(this.props.listId).columns];
        columns.push({
            name: columnName,
            string: fieldDef.string,
            hidden: false,
        });
        this.udpateListDefinition({ columns });
    }

    addCalculatedColumn() {
        const columns = [...this.getters.getListDefinition(this.props.listId).columns];
        const string = _t("New calculated column");
        const name = this.calculatedColumnName(
            columns.map((col) => col.name),
            string
        );
        columns.push({
            name,
            string,
            computedBy: { sheetId: this.env.model.getters.getActiveSheetId(), formula: "=0" },
            hidden: false,
        });
        this.udpateListDefinition({ columns });
    }

    onFormulaChange(column, newFormula) {
        const columns = [...this.getters.getListDefinition(this.props.listId).columns];
        const updatedColumnIndex = columns.findIndex((col) => col.name === column.name);
        const newSheetId = this.env.model.getters.getActiveSheetId();
        const currentCompute = columns[updatedColumnIndex]?.computedBy;
        if (currentCompute?.formula === newFormula && currentCompute.sheetId === newSheetId) {
            return;
        }
        columns[updatedColumnIndex] = {
            ...columns[updatedColumnIndex],
            computedBy: {
                sheetId: newSheetId,
                formula: newFormula,
            },
        };
        this.udpateListDefinition({ columns });
    }

    reorderColumns(columnNames) {
        const currentColumns = this.getters.getListDefinition(this.props.listId).columns;
        const columns = columnNames.map((colName) =>
            currentColumns.find((col) => col.name === colName)
        );
        this.udpateListDefinition({ columns });
    }

    toggleColumnVisibility(column) {
        const columns = [...this.getters.getListDefinition(this.props.listId).columns];
        const updatedColumnIndex = columns.findIndex((col) => col.name === column.name);
        columns[updatedColumnIndex] = {
            ...columns[updatedColumnIndex],
            hidden: !columns[updatedColumnIndex].hidden,
        };
        this.udpateListDefinition({ columns });
    }

    filterField(field, path) {
        const RELATIONAL_FIELDS = new Set(["many2one", "one2many"]);
        const fullField = path ? `${path}.${field.name}` : field.name;
        const def = this.getters.getListDefinition(this.props.listId);
        const isFieldAlreadyPresent = def.columns.some((col) => col.name === fullField);
        if (RELATIONAL_FIELDS.has(field.type)) {
            return { isFieldAlreadyPresent };
        }
        if (!isFieldAlreadyPresent) {
            return true;
        }
        return false;
    }

    getColumnFieldDisplayName(column) {
        const field = this.env.model.getters
            .getListDataSource(this.props.listId)
            .getFieldFromFieldPath(column.name);
        return field?.string || column.name;
    }

    udpateListDefinition(newPartialDefinition) {
        const listDefinition = this.getters.getListDefinition(this.props.listId);
        this.env.model.dispatch("UPDATE_ODOO_LIST", {
            listId: this.props.listId,
            list: {
                ...listDefinition,
                ...newPartialDefinition,
            },
        });
    }
}
