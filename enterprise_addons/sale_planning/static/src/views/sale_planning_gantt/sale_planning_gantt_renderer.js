import { markup } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";
import { Domain } from "@web/core/domain";
import { patch } from "@web/core/utils/patch";
import { PlanningGanttRenderer } from "@planning/views/planning_gantt/planning_gantt_renderer";

patch(PlanningGanttRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.roleIds = [];
    },
    getPlanDialogDomain() {
        let domain = super.getPlanDialogDomain(...arguments);
        if (this.roleIds.length) {
            domain = Domain.and([domain, [["role_id", "in", this.roleIds]]]);
        }
        return Domain.and([domain, Domain.not([["sale_line_id.state", "=", "cancel"]])]).toList({});
    },
    getSelectCreateDialogProps() {
        const props = super.getSelectCreateDialogProps(...arguments);
        this.model.addSpecialKeys(props.context);
        Object.assign(props.context, {
            default_start_datetime: props.context.start_datetime,
            default_end_datetime: props.context.end_datetime,
            search_default_resource_ids: false,
            search_default_sale_order_id: props.context.planning_gantt_active_sale_order_id,
        });
        props.noContentHelp = markup`
            <p class="o_view_nocontent_smiling_face">${_t("No shifts found!")}</p>
            <p>${_t(
                "Assign your sales orders to the right people based on their roles and availability."
            )}</p>`;
        return props;
    },
    /**
     * @override
     */
    async updateMultiSelection(block, action) {
        const { startRow } = block;
        const rowId = this.rowIdsByFirstRow[startRow];
        const currentRow = this.rowByIds[rowId];
        this.roleIds = (currentRow.progressBar?.role_ids) || [];
        if (this.roleIds.length || !currentRow.resId) {
            this.model.searchShiftsToPlan(this.getPlanDialogDomain(), true).then((exists) => {
                this.multiSelectionButtonsReactive.hasAvailableSOL = exists;
            });
        }
        delete this.multiSelectionButtonsReactive.hasAvailableSOL;
        return super.updateMultiSelection(block, action);
    },
    /**
     * @override
     */
    async onPlan(rowId, columnStart, columnStop) {
        let { start, stop } = this.getColumnStartStop(columnStart, columnStop);
        ({ start, stop } = this.normalizeTimeRange(start, stop));
        const schedule = this.props.model.getDialogContext({ rowId, start, stop });
        if ("sale_line_id" in schedule) {
            if (!schedule.sale_line_id) {
                this.displayFailedPlanningNotification(
                    _t("There are no sales order items to plan.")
                );
            } else {
                const slotIds = await this.props.model.searchShiftsToPlan(
                    [
                        ["sale_line_id", "=", schedule.sale_line_id],
                        ["start_datetime", "=", false],
                        ["end_datetime", "=", false],
                    ],
                    false
                );
                if (slotIds.length) {
                    const result = await this.props.model._assignSlot(slotIds, schedule);
                    this.notifyAssignSlotResult(slotIds, result);
                } else {
                    this.displayFailedPlanningNotification(
                        _t(
                            "There are no hours left to plan, or there are no resources available at the time."
                        )
                    );
                }
            }
            return;
        }
        const currentRow = this.rowByIds[rowId];
        this.roleIds = (currentRow.progressBar && currentRow.progressBar.role_ids) || [];
        const existsShiftToPlan = await this.props.model.searchShiftsToPlan(
            this.getPlanDialogDomain()
        );
        if (this.model.useSampleModel) {
            rowId = false;
        }
        if (!existsShiftToPlan) {
            return this.onCreate(rowId, columnStart, columnStop);
        }
        super.onPlan(rowId, columnStart, columnStop);
    },
});
