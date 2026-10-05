import { serializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { omit } from "@web/core/utils/objects";
import { STATIC_ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";
import { ProjectTaskCalendarController } from "@project/views/project_task_calendar/project_task_calendar_controller";

export class ProjectEnterpriseTaskCalendarController extends ProjectTaskCalendarController {
    static template = "project_enterprise.ProjectTaskCalendarController";

    setup() {
        super.setup();
        this.notifications = useService("notification");
    }

    getStaticActionMenuItems() {
        return {
            printPlanning: {
                isAvailable: () => this.model.scale !== "day",
                sequence: 10,
                icon: "print",
                description: _t("Print"),
                callback: async () => {
                    const startDate = serializeDateTime(this.model.visibleRange.start);
                    const stopDate = serializeDateTime(this.model.visibleRange.end);
                    const domain = this.model.computeDomain(this.model.data);
                    const result = await this.orm.call("project.task", "action_print_tasks", [
                        startDate,
                        stopDate,
                        domain,
                        this.model.scale,
                    ]);
                    if (result) {
                        this.action.doAction(result);
                    } else {
                        this.notifications.add(
                            _t("No tasks to print"),
                            { type: "warning" }
                        );
                    }
                },
            },
        };
    }

    get actionMenuItems() {
        const { actionMenus } = this.props.info;
        const staticActionItems = Object.entries(this.getStaticActionMenuItems())
            .filter(([key, item]) => item.isAvailable === undefined || item.isAvailable())
            .sort(([k1, item1], [k2, item2]) => (item1.sequence || 0) - (item2.sequence || 0))
            .map(([key, item]) =>
                Object.assign({ key }, omit(item, "isAvailable", "sequence"), {
                    groupNumber: STATIC_ACTIONS_GROUP_NUMBER,
                })
            );

        return {
            action: [...staticActionItems, ...(actionMenus?.action || [])],
            print: actionMenus?.print || [],
        };
    }

    get cogMenuProps() {
        return {
            items: this.props.info.actionMenus ? this.actionMenuItems : {},
            context: this.props.context,
            resModel: this.model.resModel,
            getActiveIds: () => [],
        };
    }

}
