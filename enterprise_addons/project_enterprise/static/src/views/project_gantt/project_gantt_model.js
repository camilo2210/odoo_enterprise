import { user } from "@web/core/user";
import { GanttModel } from "@web_gantt/gantt_model";
import { localStartOf } from "@web_gantt/gantt_helpers";
import { ProjectModelMixin } from "@project/views/project_model_mixin";

const COLOR_FIELD = "stage_id";

export class ProjectGanttModel extends ProjectModelMixin(GanttModel) {
    /**
     * @override
     */
    async load(searchParams) {
        const stagesEnabled = await user.hasGroup("project.group_project_stages");
        if (stagesEnabled && !this.metaData.colorField) {
            // This is equivalent to setting a color attribute for the gantt view, but only when we have read access to
            // the field (i.e. the user has the 'project.group_project_stages' group).
            this.metaData.colorField = COLOR_FIELD;
        }
        searchParams.domain = this._processSearchDomain(searchParams?.domain || []);
        await super.load(searchParams);
    }

    /**
     * @override
     */
    _reschedule(ids, data, context) {
        return this.orm.call(this.metaData.resModel, "web_gantt_write", [ids, data], {
            context,
        });
    }

    /**
     * @override
     */
    getRangeFromDate(rangeId, date) {
        const startDate = localStartOf(date, rangeId);
        const stopDate = startDate.plus({ [rangeId]: 1 }).minus({ day: 1 });
        return { focusDate: date, startDate, stopDate, rangeId };
    }
}
