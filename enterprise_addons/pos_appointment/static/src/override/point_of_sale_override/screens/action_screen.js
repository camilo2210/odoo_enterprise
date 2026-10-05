import { ActionScreen } from "@point_of_sale/app/screens/action_screen";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { patch } from "@web/core/utils/patch";
import { useEffect } from "@odoo/owl";

patch(ActionScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();

        useEffect(() => {
            if (this.props.actionName === "manage-booking") {
                this.pos.data
                    .call("calendar.event", "action_open_booking_gantt_view", [false], {
                        context: {
                            appointment_type_id: this.pos.config.raw.appointment_type_id,
                        },
                    })
                    .then((result) => {
                        this.pos.action.doAction(result);
                        if (this.props.viewMode) {
                            this.pos.action.switchView(this.props.viewMode);
                        }
                    });
            }
        });
    },
});
