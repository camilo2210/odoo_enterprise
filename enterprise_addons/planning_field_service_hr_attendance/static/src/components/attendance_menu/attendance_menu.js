import { useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";

patch(ActivityMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.fieldServiceGeolocation = useService("field_service_geolocation");

        useEffect(() => {
            if (this.state.checkedIn) {
                this.fieldServiceGeolocation.startWatch();
            } else {
                this.fieldServiceGeolocation.stopWatch();
            }
        });
    },
});
