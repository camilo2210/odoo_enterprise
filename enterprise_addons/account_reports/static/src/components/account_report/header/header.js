import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";

import { Component, usePlugin } from "@odoo/owl";

import { AccountReportController } from "@account_reports/components/account_report/controller";


export class AccountReportHeader extends Component {
    static template = "account_reports.AccountReportHeader";
    static components = {
        Dropdown,
        DropdownItem,
    };

    controller = usePlugin(AccountReportController);
    // -----------------------------------------------------------------------------------------------------------------
    // Headers
    // -----------------------------------------------------------------------------------------------------------------
    get columnHeaders() {
        const columnHeaders = [];

        this.controller.options().column_headers.forEach((columnHeader, columnHeaderIndex) => {
            let columnHeadersRow = [];
            if (columnHeaderIndex !== 0 || columnHeader.length !== 1) {
                for (let i = 0; i < this.controller.columnHeadersRenderData.level_repetitions[columnHeaderIndex]; i++) {
                    columnHeadersRow = [ ...columnHeadersRow, ...columnHeader];
                }
                columnHeaders.push(columnHeadersRow);
            }
        });
        return columnHeaders;
    }

    get companiesHeaderColspan() {
        let colspan = this.controller.options().columns.length;

        if (this.controller.needsColumnPercentComparison) {
            colspan ++;
        }
        if (this.controller.hasDebugColumn) {
            colspan ++;
        }
        return colspan + 1; // extra +1 because to add colspan for the line name column
    }

    columnHeadersColspan(column_index, header, compactOffset = 0) {
        const firstRowHeader = this.controller.options().column_headers[0];
        if (firstRowHeader.length === 1) {
            column_index += 1;
        }
        let colspan = header.colspan || this.controller.columnHeadersRenderData.level_colspan[column_index]
        // In case of we need the total column for horizontal we need to increase the colspan of the first row
        if(this.controller.options().show_horizontal_group_total && column_index === 0) {
           colspan += 1;
        }
        return colspan;
    }

    columnHeadersRowspan(header) {
        return header?.forced_options?.no_subheader_division
            ? this.controller.options().column_headers.length - 1
            : 1;
    }

    //------------------------------------------------------------------------------------------------------------------
    // Subheaders
    //------------------------------------------------------------------------------------------------------------------
    get subheaders() {
        const columns = JSON.parse(JSON.stringify(this.controller.options().columns));
        const columnsPerGroupKey = {};

        columns.forEach((column) => {
            columnsPerGroupKey[`${column.column_group_index}_${column.expression_label}`] = column;
        });

        return this.controller.lines[0].columns.map((column) => {
            if (columnsPerGroupKey[`${column.column_group_index}_${column.expression_label}`]) {
                return columnsPerGroupKey[`${column.column_group_index}_${column.expression_label}`];
            } else {
                return {
                    expression_label: "",
                    sortable: false,
                    name: "",
                    colspan: 1,
                };
            }
        });
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Custom subheaders
    // -----------------------------------------------------------------------------------------------------------------
    get customSubheaders() {
        const customSubheaders = [];

        this.controller.columnHeadersRenderData.custom_subheaders.forEach(customSubheader => {
            customSubheaders.push(customSubheader);
        });

        return customSubheaders;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Sortable
    // -----------------------------------------------------------------------------------------------------------------
    sortableClasses(columnIndex) {
        switch (this.controller.linesCurrentOrderByColumn(columnIndex)) {
            case "ASC":
                return "north";
            case "DESC":
                return "south";
            default:
                return "swap_vert";
        }
    }

    async sortLinesByColumn(columnIndex, column) {
        if (column.sortable) {
            switch (this.controller.linesCurrentOrderByColumn(columnIndex)) {
                case "default":
                    await this.controller.sortLinesByColumnAsc(columnIndex);
                    break;
                case "ASC":
                    await this.controller.sortLinesByColumnDesc(columnIndex);
                    break;
                case "DESC":
                    this.controller.sortLinesByDefault();
                    break;
                default:
                    throw new Error(`Invalid value: ${ this.controller.linesCurrentOrderByColumn(columnIndex) }`);
            }
        }
    }
}

registry.category("account_reports.default_components").add("AccountReportHeader", AccountReportHeader);
