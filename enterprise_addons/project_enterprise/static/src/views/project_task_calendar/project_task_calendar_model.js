import { ProjectTaskCalendarModel } from "@project/views/project_task_calendar/project_task_calendar_model";
import { deserializeDate } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";
import { useProjectModelActions } from "../project_highlight_tasks";

patch(ProjectTaskCalendarModel.prototype, {
    setup() {
        super.setup(...arguments);
        this.getHighlightIds = useProjectModelActions({
            getContext: () => this.env.searchModel._context,
        }).getHighlightIds;
    },

    /**
     * @override
     */
    async loadRecords(data) {
        this.highlightIds = await this.getHighlightIds();
        return await super.loadRecords(data);
    },
});

export class ProjectEnterpriseTaskCalendarModel extends ProjectTaskCalendarModel {
    makeContextDefaults(record) {
        const { default_planned_date_start, ...context } = super.makeContextDefaults(record);
        if (
            ["day", "week"].includes(this.meta.scale) ||
            !deserializeDate(default_planned_date_start).hasSame(
                deserializeDate(context["default_date_deadline"]),
                "day"
            )
        ) {
            context.default_planned_date_begin = default_planned_date_start;
        }

        return { ...context, scale: this.meta.scale };
    }
}
