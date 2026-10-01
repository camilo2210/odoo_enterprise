import { hrModels } from "@hr/../tests/hr_test_helpers";
import { hrHolidaysModels } from "@hr_holidays/../tests/hr_holidays_test_helpers";
import { defineModels } from "@web/../tests/web_test_helpers";
import { HrHolidaysGanttLeave } from "@hr_holidays_gantt/../tests/mock_server/mock_models/hr_leave";
import { HrEmployee } from "@hr_holidays_gantt/../tests/mock_server/mock_models/hr_employee";
import { M2oAvatarEmployee } from "@hr_holidays_gantt/../tests/mock_server/mock_models/m2o_avatar_employee";

export function defineHrHolidaysGanttModels() {
    return defineModels(hrHolidaysGanttModels);
}

export const hrHolidaysGanttModels = {
    ...hrModels,
    ...hrHolidaysModels,
    HrLeave: HrHolidaysGanttLeave,
    HrEmployee: HrEmployee,
    M2oAvatarEmployee: M2oAvatarEmployee,
};
