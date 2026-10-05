import { Activity } from "@mail/core/web/activity";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

patch(Activity.prototype, {
    setup() {
        super.setup();
        this.user = user.userId;

        this.notification = useService("notification");
        this.action = useService("action");
    },

    get signRequest() {
        return this.store["sign.request"].records
            .values()
            .find((record) => record.id === this.activity().sign_request_id);
    },

    get signTemplate() {
        return this.store["sign.template"].records
            .values()
            .find((record) => record.id === this.activity().sign_template_id);
    },

    get requestValidity() {
        const validity = this.signRequest?.validity;
        return validity
            ? validity.toLocaleString({ month: "short", day: "numeric", year: "numeric" })
            : _t("Awaiting signature");
    },

    onClickViewSignRequestDocuments() {
        this.activity().viewSignRequestDocuments();
    },

    onClickResendSignRequest() {
        this.activity().resendSignatureAccesses();
    },

    onClickSignNow() {
        this.activity().goToSignableDocument();
    },

    onClickRequestSign() {
        this.activity().requestSignature(this.signTemplate?.id);
    },

    edit() {
        if (this.signRequest) {
            this.activity().openSignRequestForm();
        } else {
            super.edit(...arguments);
        }
    },

    onClickAvatar(ev) {
        if (this.signRequest) {
            // Prevent the popup when activity img is clicked
            ev?.stopPropagation();
            ev?.preventDefault();
            return;
        }
        return super.onClickAvatar(ev);
    },
});
