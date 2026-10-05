import { localization } from "@web/core/l10n/localization";
import { usePopover } from "@web/core/popover/popover_hook";

import { GanttPopover } from "@web_gantt/gantt_popover";
import { GanttRenderer } from "@web_gantt/gantt_renderer";

import { MilestonesPopover } from "./milestones_popover";

import { onMounted, t, useProps } from "@odoo/owl";

class TaskGanttPopover extends GanttPopover {
    ownProps = useProps({
        context: t.object().optional(),
    });

    get cardPopoverProps() {
        const props = super.cardPopoverProps;
        props.context = { ...props.context, ...this.ownProps.context };
        return props;
    }
}

export class TaskGanttRendererCommon extends GanttRenderer {
    static headerTemplate = "project_enterprise.TaskGanttRenderer.Header";
    static rowContentTemplate = "project_enterprise.TaskGanttRenderer.RowContent";
    static totalRowTemplate = "project_enterprise.TaskGanttRenderer.TotalRow";
    static pillTemplate = "project_enterprise.TaskGanttRenderer.Pill";
    static components = {
        ...GanttRenderer.components,
        Popover: TaskGanttPopover,
    }

    setup() {
        super.setup(...arguments);
        onMounted(() => this.gridRef().classList.add("o_project_gantt"));
        const position = localization.direction === "rtl" ? "bottom" : "right";
        this.milestonePopover = usePopover(MilestonesPopover, { position });
    }

    /**
     * @override
     */
    enrichPill(pill) {
        const enrichedPill = super.enrichPill(pill);
        if (enrichedPill.record.is_closed) {
            pill.className += " opacity-50";
        }
        return enrichedPill;
    }

    /**
     * Sparse task rows have no group-by field and incorrectly reused the Total bar.
     *
     * @override
     */
    getRowProgressBar(groupedByField, resId) {
        if (!groupedByField && resId) {
            const record = this.model.data.records.find((r) => r.id === resId);
            const allocatedHours = record?.allocated_hours ?? 0;
            if (allocatedHours > 0) {
                return this.model._processProgressBar({ value: 0, max_value: allocatedHours }, null);
            }
            return null;
        }
        return super.getRowProgressBar(groupedByField, resId);
    }

    /**
     * Hide the progress-bar track on sparse task leaf rows while keeping
     * the progress label (allocated time) in the row header.
     *
     * @override
     */
    progressBarIsVisible(row) {
        if (!row.groupedByField && row.resId) {
            return false;
        }
        return super.progressBarIsVisible(row);
    }

    computeVisibleColumns() {
        super.computeVisibleColumns();
        this.columnMilestones = {}; // deadlines and milestones by project
        for (const column of this.columns) {
            this.columnMilestones[column.index] = {
                hasDeadLineExceeded: false,
                allReached: true,
                projects: {},
                hasMilestone: false,
                hasDeadline: false,
                hasStartDate: false,
            };
        }
        // Handle start date at the beginning of the current period
        this.columnMilestones[this.columns[0].index].edge = {
            projects: {},
            hasStartDate: false,
        };
        const projectStartDates = [...this.model.data.projectStartDates];
        const projectDeadlines = [...this.model.data.projectDeadlines];
        const milestones = [...this.model.data.milestones];

        let project = projectStartDates.shift();
        let projectDeadline = projectDeadlines.shift();
        let milestone = milestones.shift();
        let i = 0;
        while (i < this.columns.length && (project || projectDeadline || milestone)) {
            const column = this.columns[i];
            const nextColumn = this.columns[i + 1];
            const info = this.columnMilestones[column.index];

            if (i == 0 && project && column && column.stop > project.date) {
                // For the first column, start dates have to be displayed at the start of the period
                if (!info.edge.projects[project.id]) {
                    info.edge.projects[project.id] = {
                        milestones: [],
                        id: project.id,
                        name: project.name,
                    };
                }
                info.edge.projects[project.id].isStartDate = true;
                info.edge.hasStartDate = true;
                project = projectStartDates.shift();
            } else if (project && nextColumn?.stop > project.date) {
                if (!info.projects[project.id]) {
                    info.projects[project.id] = {
                        milestones: [],
                        id: project.id,
                        name: project.name,
                    };
                }
                info.projects[project.id].isStartDate = true;
                info.hasStartDate = true;
                project = projectStartDates.shift();
            }

            if (projectDeadline && column.stop > projectDeadline.date) {
                if (!info.projects[projectDeadline.id]) {
                    info.projects[projectDeadline.id] = {
                        milestones: [],
                        id: projectDeadline.id,
                        name: projectDeadline.name,
                    };
                }
                info.projects[projectDeadline.id].isDeadline = true;
                info.hasDeadline = true;
                projectDeadline = projectDeadlines.shift();
            }

            if (milestone && column.stop > milestone.deadline) {
                const [projectId, projectName] = milestone.project_id;
                if (!info.projects[projectId]) {
                    info.projects[projectId] = {
                        milestones: [],
                        id: projectId,
                        name: projectName,
                    };
                }
                const { is_deadline_exceeded, is_reached } = milestone;
                info.projects[projectId].milestones.push(milestone);
                info.hasMilestone = true;
                milestone = milestones.shift();
                if (is_deadline_exceeded) {
                    info.hasDeadLineExceeded = true;
                }
                if (!is_reached) {
                    info.allReached = false;
                }
            }
            if (
                (!project || !nextColumn || nextColumn?.stop < project.date) &&
                (!projectDeadline || column.stop < projectDeadline.date) &&
                (!milestone || column.stop < milestone.deadline)
            ) {
                i++;
            }
        }
    }

    getPopoverProps() {
        const props = super.getPopoverProps(...arguments);
        props.context = { is_form_gantt: true };
        return props;
    }

    shouldRenderRecordConnectors(record) {
        if (record.allow_task_dependencies) {
            return super.shouldRenderRecordConnectors(...arguments);
        }
        return false;
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    onMilestoneMouseEnter(ev, projects) {
        this.milestonePopover.open(ev.target, {
            displayMilestoneDates: this.model.metaData.scale.id === "year",
            displayProjectName: !this.model.searchParams.context.default_project_id,
            projects,
        });
    }

    onMilestoneMouseLeave() {
        this.milestonePopover.close();
    }

    //--------------------------------------------------------------------------
    //Task Connectors
    //--------------------------------------------------------------------------

    shouldConnectorBeDashed(sourcePill) {
        if (sourcePill.record.is_closed) {
            return true;
        }
        return super.shouldConnectorBeDashed(sourcePill);
    }

}
