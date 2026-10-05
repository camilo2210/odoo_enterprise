import { GridRenderer } from "@web_grid/views/grid_renderer";

export class MarginAnalyticLineGridRenderer extends GridRenderer {
    getSectionTotalRowClass(section, grandTotal) {
        return {
            ...super.getSectionTotalRowClass(section, grandTotal),
            "bg-view": false,
        };
    }

    getTotalCellsTextClasses(row, grandTotal) {
        const isSection = this.props.model.sectionField;
        return {
            ...super.getTotalCellsTextClasses(row, grandTotal),
            "bg-view": grandTotal == 0,
            "bg-danger text-bg-danger": grandTotal < 0 && !isSection,
            "bg-success text-bg-success": grandTotal > 0 && !isSection,
        };
    }

    getSectionCellsClasses(column, row) {
        return {
            ...super.getSectionCellsClasses(column, row),
            "text-danger": row.cells[column.id].value < 0,
            "text-success": row.cells[column.id].value > 0,
        };
    }

    getTextColorClasses(column, row, isEven) {
        return {
            ...super.getTextColorClasses(column, row, isEven),
            "text-danger": false,
        };
    }

    _getTotalCellBgColor(section, grandTotal) {
        if (grandTotal < 0) {
            return "text-bg-danger";
        } else if (grandTotal > 0) {
            return "text-bg-success";
        }
        return "bg-200";
    }

    getFooterTotalCellClasses(grandTotal) {
        if (grandTotal < 0) {
            return "text-bg-danger bg-opacity-75";
        } else if (grandTotal > 0) {
            return "text-bg-success bg-opacity-75";
        }
        return super.getFooterTotalCellClasses(grandTotal);
    }

    getColumnTotalClassNames(column) {
        if (column.grandTotal < 0) {
            return "text-danger";
        } else if (column.grandTotal > 0) {
            return "text-success";
        }
        return "";
    }
}
