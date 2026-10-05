import { Component, onWillUnmount, proxy, signal, t, useProps } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { deserializeDate, serializeDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { useModelWithSampleData } from "@web/model/model";
import { useSetupAction } from "@web/search/action_hook";
import { CogMenu } from "@web/search/cog_menu/cog_menu";
import { Layout } from "@web/search/layout";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { useSearchBarToggler } from "@web/search/search_bar/search_bar_toggler";
import { ActionHelper } from "@web/views/action_helper";
import { standardViewProps } from "@web/views/standard_view_props";
import { ViewButton } from "@web/views/view_button/view_button";
import { useViewButtons } from "@web/views/view_button/view_button_hook";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { GridModel } from "./grid_model";
import { GridRenderer } from "./grid_renderer";

const { DateTime } = luxon;

export class GridController extends Component {
    static components = {
        Layout,
        Dropdown,
        DropdownItem,
        ViewButton,
        CogMenu,
        SearchBar,
        ActionHelper,
    };
    static template = "web_grid.GridView";

    props = useProps({
        ...standardViewProps,
        archInfo: t.object(),
        buttonTemplate: t.string(),
        Model: t.constructor(GridModel),
        Renderer: t.constructor(GridRenderer),
    });

    rootRef = signal.ref(HTMLDivElement);

    setup() {
        this.uiService = useService("ui");
        const state = this.props.state || {};
        let activeRangeName = this.props.archInfo.activeRangeName;
        let defaultAnchor;
        if (state.activeRangeName) {
            activeRangeName = state.activeRangeName;
        } else if (this.uiService.isSmall && "day" in this.props.archInfo.ranges) {
            activeRangeName = "day";
        }
        if (state.anchor) {
            defaultAnchor = state.anchor;
        } else if (this.props.context.grid_anchor) {
            defaultAnchor = deserializeDate(this.props.context.grid_anchor);
        }
        this.dialogService = useService("dialog");
        this.model = useModelWithSampleData(this.props.Model, {
            resModel: this.props.resModel,
            sectionField: this.props.archInfo.sectionField,
            rowFields: this.props.archInfo.rowFields,
            columnFieldName: this.props.archInfo.columnFieldName,
            measureField: this.props.archInfo.measureField,
            readonlyField: this.props.archInfo.readonlyField,
            fieldsInfo: this.props.relatedModels[this.props.resModel].fields,
            activeRangeName,
            ranges: this.props.archInfo.ranges,
            defaultAnchor,
        });
        useSetupAction({
            rootRef: this.rootRef,
            getLocalState: () => {
                const { anchor, range } = this.model.navigationInfo;
                return {
                    anchor,
                    activeRangeName: range?.name,
                };
            },
        });
        const isWeekendVisible = browser.localStorage.getItem("grid.isWeekendVisible");
        this.state = proxy({
            activeRangeName: this.model.navigationInfo.range?.name,
            isWeekendVisible:
                isWeekendVisible !== null && isWeekendVisible !== undefined
                    ? JSON.parse(isWeekendVisible)
                    : true,
        });
        useViewButtons(this.rootRef, {
            beforeExecuteAction: this.beforeExecuteActionButton.bind(this),
            afterExecuteAction: this.afterExecuteActionButton.bind(this),
            reload: this.reload.bind(this),
        });
        onWillUnmount(() => this.closeDialog?.());
        this.searchBarToggler = useSearchBarToggler();
    }

    get isEditable() {
        return this.props.archInfo.activeActions.edit && this.props.archInfo.editable;
    }

    get displayNoContent() {
        return (
            !(this.props.archInfo.displayEmpty || this.model.hasData()) || this.model.useSampleModel
        );
    }

    get displayAddALine() {
        return this.props.archInfo.activeActions.create;
    }

    get hasDisplayableData() {
        return true;
    }

    get options() {
        const { hideLineTotal, hideColumnTotal, hasBarChartTotal, createInline } =
            this.props.archInfo;
        return {
            hideLineTotal,
            hideColumnTotal,
            hasBarChartTotal,
            createInline,
        };
    }

    createRecord(params) {
        const columnContext = this.model.columnFieldIsDate
            ? {
                  [`default_${this.model.columnFieldName}`]: serializeDate(
                      this.model.navigationInfo.anchor
                  ),
              }
            : {};
        const context = {
            ...this.props.context,
            ...columnContext,
            ...(params?.context || {}),
        };
        this.closeDialog = this.dialogService.add(
            FormViewDialog,
            {
                title: _t("New Record"),
                resModel: this.model.resModel,
                viewId: this.props.archInfo.formViewId,
                onRecordSaved: this.onRecordSaved.bind(this),
                ...(params || {}),
                context,
            },
            {
                onClose: () => {
                    this.closeDialog = null;
                },
            }
        );
    }

    async beforeExecuteActionButton() {}

    async afterExecuteActionButton() {}

    async reload() {
        await this.model.reload();
    }

    async onRecordSaved(record) {
        await this.reload();
    }

    get columns() {
        return this.state.isWeekendVisible || ["day", "year"].includes(this.state.activeRangeName)
            ? this.model.columnsArray
            : this.model.columnsArray.filter(
                  (column) => DateTime.fromISO(column.value).weekday < 6
              );
    }

    toggleWeekendVisibility() {
        this.state.isWeekendVisible = !this.state.isWeekendVisible;
        browser.localStorage.setItem("grid.isWeekendVisible", this.state.isWeekendVisible);
    }
}
