import { defineModels } from "@web/../tests/web_test_helpers";
import { planningModels } from "@planning/../tests/planning_mock_models";
import { hrHolidaysModels } from "@hr_holidays/../tests/hr_holidays_test_helpers";

export function definePlanningHolidaysModels() {
    return defineModels(planningHolidaysModels);
}

export const planningHolidaysModels = { ...planningModels, ...hrHolidaysModels };
