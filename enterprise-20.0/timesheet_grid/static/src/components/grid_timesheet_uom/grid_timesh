import { useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";

import { GridCell } from "@web_grid/components/grid_cell";
import { standardGridCellProps } from "@web_grid/hooks/grid_cell_hook";

import { TimesheetUOM } from "@hr_timesheet/components/timesheet_uom/timesheet_uom";

export class GridTimesheetUOM extends TimesheetUOM {
    props = useProps(standardGridCellProps);

    /**
     * @override
     */
    getTimesheetComponent(fieldName) {
        return registry.category("grid_components").get(fieldName, { component: GridCell })
            .component;
    }
}
