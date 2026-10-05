import { t, useEffect, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { addFieldDependencies } from "@web/model/relational_model/utils";
import {
    MultiSelectionButtons,
    multiSelectionButtonsProps,
} from "@web/views/view_components/multi_selection_buttons";
import { usePopover } from "@web/core/popover/popover_hook";

export class HrHolidaysGanttMultiSelectionButtons extends MultiSelectionButtons {
    static template = "hr_holidays_gantt.HrHolidaysGanttMultiSelectionButtons";
    props = useProps({
        reactive: t.object({
            ...multiSelectionButtonsProps.reactive.toShape(),
            onPlan: t.function().optional(),
            onQuickAddDirect: t.function().optional(),
            pendingAdd: t.boolean().optional(),
            nbSelectedCells: t.number().optional(),
            nbSelectedRows: t.number().optional(),
            forceFullDuration: t.boolean().optional(),
            singleCellStop: t.object().optional(),
            employeeId: t.number().optional(),
            start: t.object().optional(),
            stop: t.object().optional(),
            isMultiEmployee: t.boolean().optional(),
            noAllocationWorkTypes: t.array().optional(),
            allocatedWorkTypes: t.array().optional(),
        }),
    });
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.multiCreatePopover = usePopover(this.constructor.components.Popover, {
            popoverClass: "o_hr_holidays_gantt_multi_create_popover",
            onClose: () => {
                const multiCreateData = this.getMultiCreateDataFromPopover();
                if (multiCreateData) {
                    this.storeMultiCreateData(multiCreateData);
                }
            },
        });
        useEffect(() => {
            if (this.props.reactive.pendingAdd && this.addButtonRef()) {
                this.props.reactive.pendingAdd = false;
                this.onAdd();
            }
        });
    }

    /**
     * @override
     */
    getMultiCreatePopoverProps() {
        const props = super.getMultiCreatePopoverProps();
        const forceFullDuration = !!this.props.reactive.forceFullDuration;
        const employeeId = this.props.reactive.employeeId;
        const { start, stop, singleCellStop, nbSelectedCells, isMultiEmployee } = this.props.reactive;
        // A single day selection highlights both morning and afternoon cells (2 cells).
        // Therefore, anything > 2 means multiple days are selected.
        const isMultiDay = nbSelectedCells > 2;

        const requestRangeStop = stop ? stop.minus({ second: 1 }) : undefined;
        const singleRangeStop = singleCellStop ? singleCellStop.minus({ second: 1 }) : undefined;

        props.multiCreateRecordProps.context = {
            ...props.multiCreateRecordProps.context,
            force_full_duration: forceFullDuration,
            default_employee_id: employeeId,
            default_request_date_from: start?.toISODate?.(),
            default_request_date_to: requestRangeStop?.toISODate?.(),
            gantt_full_request_date_to: requestRangeStop?.toISODate?.(),
            gantt_single_request_date_to: singleRangeStop?.toISODate?.(),
            is_multi_day_selection: isMultiDay,
            default_is_multi_employee: isMultiEmployee,
            employee_id: employeeId,
            is_popover: true,
        };

        props.multiCreateRecordProps.values = undefined;
        return props;
    }

    get multiCreateAdditionalFieldDependencies() {
        return [
            { name: "display_code", type: "char" },
            { name: "color", type: "integer" },
        ];
    }

    /**
     * @override
     */
    async loadMultiCreateView() {
        await super.loadMultiCreateView();
        const extraDependencies = this.multiCreateAdditionalFieldDependencies.filter(
            (field) => field.name in this.multiCreateRecordProps.fields
        );
        addFieldDependencies(
            this.multiCreateRecordProps.activeFields,
            this.multiCreateRecordProps.fields,
            extraDependencies
        );
    }

    /**
     * @override
     */
    makeValues(workEntryTypeId) {
        const values = {
            work_entry_type_id: workEntryTypeId?.id,
        };
        if (this.props.reactive.forceFullDuration) {
            values.request_duration = "full";
        }
        return values;
    }

    async onQuickAddDirect(workEntryType) {
        const values = this.makeValues(workEntryType);
        this.props.reactive.onQuickAddDirect(values);
    }

}
