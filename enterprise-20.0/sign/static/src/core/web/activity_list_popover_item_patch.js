import { ActivityListPopoverItem } from "@mail/core/web/activity_list_popover_item";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

patch(ActivityListPopoverItem.prototype, {
    setup() {
        super.setup();
        this.user = user.userId;
        this.needMySignature = false;
        this.orm = useService("orm");

        onWillStart(async () => {
            if (this.activity().sign_request_id) {
                const result = await this.orm.searchRead(
                    "sign.request",
                    [["id", "=", this.activity().sign_request_id]],
                    ["need_my_signature"]
                );
                this.needMySignature = result[0]?.need_my_signature || false;
            }
        });
    },

    get hasMarkDoneButton() {
        return super.hasMarkDoneButton && this.activity().activity_category !== "sign_request";
    },

    get showRequestSignButton() {
        const activity = this.activity();
        return (
            !activity.sign_request_id &&
            activity.activity_category === "sign_request" &&
            activity.res_model !== "sign.request"
        );
    },

    onClickEditActivityButton() {
        if (this.activity().sign_request_id) {
            this.activity().openSignRequestForm();
        } else {
            super.onClickEditActivityButton(...arguments);
        }
    },

    onClickResendSignRequest() {
        this.activity().resendSignatureAccesses();
    },

    onClickSignNow() {
        this.activity().goToSignableDocument();
    },

    onClickRequestSign() {
        this.activity().requestSignature();
    },
});
