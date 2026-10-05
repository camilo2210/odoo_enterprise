import { ListRenderer } from "@web/views/list/list_renderer";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { proxy } from "@odoo/owl";

const STORAGE_KEY = "hr_payroll.display_all_payslip_lines";
export const payslipShowAllState = proxy({ showAll: JSON.parse(localStorage.getItem(STORAGE_KEY)) || false });

export class PayslipListRowVisibilityRenderer extends ListRenderer {
    static rowsTemplate = "hr_payroll.PayslipListRowVisibility";

    getCellClass(column, record) {
        let classNames = super.getCellClass(column, record);
        if (column.attrs && column.attrs.is_default_value) {
            const isDefaultValue = evaluateBooleanExpr(
                column.attrs.is_default_value,
                record.evalContextWithVirtualIds
            );
            if (isDefaultValue) {
                if (payslipShowAllState.showAll) {
                    classNames += " text-muted";
                } else {
                    classNames += " invisible";
                }
            }
        }
        return classNames;
    }

    get VisibleRows() {
        return this.props.list.records.filter((record) => {
            if (payslipShowAllState.showAll) {
                return true;
            }
            const appears = record.data.appears_on_payslip;
            return appears === 'always' || (appears === 'non_zero' && record.data.total !== 0);
        });
    }
}
