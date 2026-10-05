import { AddSocialStreamDialog } from "@social/js/add_stream_modal";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(AddSocialStreamDialog.prototype, {
    /**
     * Disable the "onclick" event for personal LinkedIn account.
     * The `pointer-event` CSS attribute can't be used for that because
     * it will disable the hover effects.
     */
    _onClickSocialAccount(event) {
        const accountId = parseInt(event.currentTarget.dataset.accountId);
        const account = this.props.socialAccounts.find((a) => a.id === accountId);
        if (account?.media_type === "linkedin" && account?.linkedin_is_personal_account) {
            return;
        }
        return super._onClickSocialAccount(...arguments);
    },

    get personalAccountTitle() {
        return _t("You cannot add a stream for a personal LinkedIn account.");
    },

    /**
     * Show the LinkedIn cards at the end.
     */
    get medias() {
        return super.medias.toSorted(
            (a, b) => (a.media_type === "linkedin") - (b.media_type === "linkedin")
        );
    },
});
