import { projectTaskCalendarView } from "@project/views/project_task_calendar/project_task_calendar_view";
import { ProjectEnterpriseTaskCalendarModel } from "./project_task_calendar_model";
import { ProjectEnterpriseTaskCalendarController } from "./project_task_calendar_controller";

projectTaskCalendarView.Model = ProjectEnterpriseTaskCalendarModel;
projectTaskCalendarView.Controller = ProjectEnterpriseTaskCalendarController;
