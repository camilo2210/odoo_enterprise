import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    get mainButton() {
        return this.pos.router.currentScreen() === "ActionScreen" &&
            this.pos.router.currentScreenParams().actionName === "manage-booking"
            ? "booking"
            : super.mainButton;
    },
});
