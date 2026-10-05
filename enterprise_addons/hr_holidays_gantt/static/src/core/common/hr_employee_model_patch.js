import { HrEmployee } from "@hr/core/common/hr_employee_model";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").HrEmployee} */
const hrEmployeePatch = {
    setup() {
        super.setup(...arguments);
        /** @type {string[]|undefined} */
        this.avatar_leave_summary = undefined;
    },
};
patch(HrEmployee.prototype, hrEmployeePatch);
