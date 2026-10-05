import { GanttController } from "@web_gantt/gantt_controller";
import { serializeDateTime } from "@web/core/l10n/dates";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { omit } from "@web/core/utils/objects";
import { STATIC_ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";

import { ProjectTaskTemplateDropdown } from "@project/views/components/project_task_template_dropdown";

export class TaskGanttController extends GanttController {
    static components = {
        ...GanttController.components,
        ProjectTaskTemplateDropdown,
    };
    static template = "project_enterprise.TaskGanttController";

    setup() {
        super.setup();
        this.notifications = useService("notification");
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
        };
    }

    get cogMenuProps() {
        return {
            items: this.props.info.actionMenus ? this.actionMenuItems : {},
        };
    }

    getStaticActionMenuItems() {
        return {
            printPlanning: {
                isAvailable: () => this.model.metaData.rangeId !== "day",
                sequence: 10,
                icon: "print",
                description: _t("Print"),
                callback: async () => {
                    const startDate = serializeDateTime(this.model.metaData.startDate);
                    const stopDate = serializeDateTime(this.model.metaData.stopDate);
                    const domain = this.model._getDomain(this.model.metaData);
                    const result = await this.orm.call("project.task", "action_print_tasks", [
                        startDate,
                        stopDate,
                        domain,
                        this.model.metaData.scale.unit,
                        this.model.metaData.scale.cellTime,
                    ]);
                    if (result) {
                        this.actionService.doAction(result);
                    } else {
                        this.notifications.add(
                            _t(
                                "No tasks to print"
                            ),
                            { type: "warning" }
                        );
                    }
                },
            },
        }
    }
}
