import { computed } from "@odoo/owl";

import { AccountReportLineCell } from "@account_reports/components/account_report/line_cell/line_cell";
import { AccountReportLineCellEditableBoolean } from "./line_cell_editable_boolean";
import { AccountReportLineCellEditableDateTime } from "./line_cell_editable_datetime";
import { AccountReportLineCellEditableLiteral } from "./line_cell_editable_literal";
import { AccountReportLineCellEditableMany2One } from "./line_cell_editable_many2one";
import { AccountReportLineCellEditableSelection } from "./line_cell_editable_selection";


export class AccountReportLineCellEditable extends AccountReportLineCell {
    static template = "account_reports.AccountReportLineCellEditable";
    static components = {
        AccountReportLineCellEditableBoolean,
        AccountReportLineCellEditableDateTime,
        AccountReportLineCellEditableLiteral,
        AccountReportLineCellEditableMany2One,
        AccountReportLineCellEditableSelection,
    };

    figureType = computed(() => this.props.cell.figure_type());
    hasEditPopupData = computed(() => Boolean(this.props.cell.edit_popup_data?.()));
    isSelection = computed(() => Boolean(this.hasEditPopupData() && this.props.cell.edit_popup_data().includes("selection_options")));

    async onChange(editValue) {
        const cellEditData = this.hasEditPopupData()
            ? JSON.parse(this.props.cell.edit_popup_data())
            : {};

        const res = await this.orm.call(
            "account.report",
            "action_modify_manual_value",
            [
                this.controller.options().report_id,
                this.props.line.id(),
                this.controller.options(),
                cellEditData.column_group_index,
                editValue,
                cellEditData.target_expression_id,
                cellEditData.rounding,
                this.controller.columnGroupsTotals,
            ],
            {
                context: this.controller.context,
            },
        );
        this.controller.lines = res.lines;
        this.controller.columnGroupsTotals = res.column_groups_totals;
    }

    getCellClasses() {
        let classes = super.getCellClasses();
        if (this.hasEditPopupData()) classes += " editable-cell";
        return classes;
    }

    get editableCellProps() {
        return {
            cell: this.props.cell,
            onChange: this.onChange.bind(this),
            audit: this.audit.bind(this),
        };
    }
}
