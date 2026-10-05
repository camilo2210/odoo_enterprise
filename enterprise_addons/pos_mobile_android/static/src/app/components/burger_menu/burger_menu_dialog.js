import { BurgerMenuDialog } from "@point_of_sale/app/components/navbar/burger_menu/burger_menu_dialog";
import { patch } from "@web/core/utils/patch";
import {
    addPosHomeShortcut,
    canAddHomeShortcut,
} from "@pos_mobile_android/app/utils/home_shortcut";

patch(BurgerMenuDialog.prototype, {
    installApp() {
        if (!canAddHomeShortcut()) {
            window.open(this.appUrl);
            return;
        }
        this.props.close();
        addPosHomeShortcut(this.pos.config).catch((error) => console.error(error));
    },
});
