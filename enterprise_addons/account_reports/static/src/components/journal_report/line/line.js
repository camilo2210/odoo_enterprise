import { computed } from "@odoo/owl";

import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportLine } from "@account_reports/components/account_report/line/line";


export class JournalReportLine extends AccountReportLine {
    static template = "account_reports.JournalReportLine";

    taxCountryQuantity = computed(() =>
        this.props.line.tax_report_lines
        ? Object.values(this.props.line.tax_report_lines).reduce((total, taxes) => total + taxes.length ? 1 : 0, 0)
        : 0
    );
    hasTaxReportLines = computed(() => this.taxCountryQuantity() > 0);
    hasTaxesSeveralCountries = computed(() => this.taxCountryQuantity() > 1);

    taxGridsCountryQuantity = computed(() => 
        this.props.line.tax_grid_summary_lines
        ? Object.values(this.props.line.tax_grid_summary_lines).reduce(
            (total, grid) => total + Object.values(grid).filter(values => values['impact']() !== undefined).length ? 1 : 0,
            0,
        ): 0
    );
    hasTaxGrids = computed(() => this.taxGridsCountryQuantity() > 0);
    hasTaxGridsSeveralCountries = computed(() => this.taxGridsCountryQuantity() > 1);

    // -----------------------------------------------------------------------------------------------------------------
    // Classes
    // -----------------------------------------------------------------------------------------------------------------
    getLineClasses() {
        let classes = super.getLineClasses();

        if (this.props.line.id().includes("|headers~~"))
            classes += ' accent_header';

        if (this.props.line.move_id?.())
            classes += ' accent_line';

        return classes;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Actions
    // -----------------------------------------------------------------------------------------------------------------
    async openTaxJournalItems(ev, name, taxType) {
        return this.controller.reportAction(ev, "journal_report_action_open_tax_journal_items", {
            name: name,
            tax_type: taxType,
            journal_id: this.props.line.journal_id?.(),
            journal_type: this.props.line.journal_type?.(),
            date_form: this.props.line.date_from?.(),
            date_to: this.props.line.date_to?.(),
        });
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Virtual Grid
    // -----------------------------------------------------------------------------------------------------------------
    static getLineHeight(controller, side, line, normalLineHeight) {
        let height = super.getLineHeight(controller, side, line, normalLineHeight);

        if (height === 0) return height;
        if (!line.is_tax_section_line) return height;

        height = normalLineHeight * 4; // 2 empty lines as margin top and bottom + 2 lines for the thead

        const table_heights = [0];  // the tables are side by side, we need to find the longest one.
        for (const taxes of Object.values(line.tax_report_lines)) {
            table_heights.push(normalLineHeight * taxes.length);
        }
        for (const grid of Object.values(line.tax_grid_summary_lines)) {
            table_heights.push(normalLineHeight * Object.keys(grid).length);
        }
        height += Math.max(...table_heights);

        return height;
    }
}

AccountReportController.registerCustomComponent(JournalReportLine);
