/** @ts-check */

import { stores, components } from "@odoo/o-spreadsheet";
import { onWillStart, Component, t, useProps } from "@odoo/owl";
import { FilterEditorStore } from "../../filter_editor_store";
import { FilterEditorFieldMatching } from "./filter_editor_field_matching";
import { GlobalFilterFooter } from "../global_filter_footer/global_filter_footer";
import { _t } from "@web/core/l10n/translation";
import { getEmptyFilterValue } from "@spreadsheet/global_filters/helpers";

const { Checkbox, Section, SidePanelCollapsible, TextInput, ValidationMessages } = components;
const { useLocalStore } = stores;

/**
 * @typedef {import("@spreadsheet").OdooField} OdooField
 * @typedef {import("@spreadsheet").FieldMatching} FieldMatching
 * @typedef {import("@spreadsheet").GlobalFilter} GlobalFilter
 *
 * @typedef State
 * @property {boolean} saved
 * @property {string} label label of the filter
 */

/**
 * This is the side panel to define/edit a global filter.
 * It can be of 3 different type: text, date and relation.
 */
export class AbstractFilterEditorSidePanel extends Component {
    static template = "";
    static components = {
        SidePanelCollapsible,
        Checkbox,
        Section,
        TextInput,
        FilterEditorFieldMatching,
        GlobalFilterFooter,
        ValidationMessages,
    };

    props = useProps({
        id: t.string().optional(),
        label: t.string().optional(),
        fieldMatching: t.object().optional(),
        onCloseSidePanel: t.function().optional(),
        onClickCancel: t.function().optional(),
        field: t.object().optional(),
    });

    setup() {
        this.store = useLocalStore(FilterEditorStore, useProps(), this.type);
        onWillStart(async () => {
            await this.store.loadData;
            if (this.props.field) {
                this.store.fieldsMatching.forEach((fieldMatching, i) => {
                    const fields = fieldMatching.fields();
                    if (fields?.[this.props.field.name]?.string === this.props.field.string) {
                        this.store.updateFieldMatching(i, this.props.field.name, this.props.field);
                    }
                });
            }
        });
    }

    get type() {
        throw new Error("Not implemented by children");
    }

    /**
     * @param {String} label
     */
    setLabel(label) {
        this.store.update({ label });
    }

    updateOperator(operator) {
        const previousValue = this.store.filter.defaultValue;
        const emptyValue = getEmptyFilterValue(this.store.filter, operator);
        this.store.update({ defaultValue: { ...emptyValue, ...previousValue, operator } });
    }

    updateDefaultValue(value) {
        if (value) {
            this.store.update({ defaultValue: value });
        } else {
            const filter = this.store.filter;
            this.store.update({
                defaultValue: {
                    ...filter.defaultValue,
                    ...getEmptyFilterValue(filter, filter.defaultValue?.operator),
                },
            });
        }
    }

    get footerProps() {
        return {
            onClickSave: !this.store.isValid
                ? undefined
                : () => {
                      const sourcePanel = `${this.constructor.name}_${this.props.id}`;
                      this.store.saveGlobalFilter(sourcePanel);
                  },
            onClickDelete: !this.props.id
                ? undefined
                : () => {
                      if (this.props.id) {
                          this.env.model.dispatch("REMOVE_GLOBAL_FILTER", { id: this.props.id });
                      }
                      this.env.replaceSidePanel(
                          "GLOBAL_FILTERS_SIDE_PANEL",
                          `${this.constructor.name}_${this.props.id}`
                      );
                  },
            onClickCancel: () => {
                this.props.onClickCancel
                    ? this.props.onClickCancel(`${this.constructor.name}_${this.props.id}`)
                    : this.env.replaceSidePanel(
                          "GLOBAL_FILTERS_SIDE_PANEL",
                          `${this.constructor.name}_${this.props.id}`
                      );
            },
        };
    }

    get invalidModel() {
        return _t(
            "At least one data source has an invalid model. Please delete it before editing this global filter."
        );
    }
}
