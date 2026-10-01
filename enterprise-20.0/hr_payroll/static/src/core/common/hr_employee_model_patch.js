import { HrEmployee } from "@hr/core/common/hr_employee_model";

import { patch } from "@web/core/utils/patch";

patch(HrEmployee.prototype, {
    setup() {
        super.setup();
        /** @type {number|undefined} */
        this.hourly_wage = undefined;
        /** @type {number|undefined} */
        this.wage = undefined;
        /** @type {string|undefined} */
        this.wage_type = undefined;
    },
});
