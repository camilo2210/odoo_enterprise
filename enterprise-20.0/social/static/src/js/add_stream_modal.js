import { Dialog } from '@web/core/dialog/dialog';
import { FormViewDialog } from '@web/views/view_dialogs/form_view_dialog';
import { useOwnedDialogs, useService } from '@web/core/utils/hooks';
import { Component, signal, t, useProps } from "@odoo/owl";
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';
import { _t } from '@web/core/l10n/translation';

export class AddSocialStreamDialog extends Component {
    static components = { Dialog };
    static template = "social.AddSocialStreamDialog";

    props = useProps({
        socialAccounts: t.array(),
        isSocialManager: t.boolean(),
        onSaved: t.function(),
        close: t.function(),
        socialMedia: t.array(),
        companies: t.array(),
    });

    setup() {
        super.setup();
        this.dialog = useService('dialog');
        this.modalRef = signal.ref();
        this.orm = useService('orm');
        this.action = useService("action");
        this.addDialog = useOwnedDialogs();
    }

    _onClickSocialAccount(event) {
        const target = event.currentTarget;
        this.dialog.add(FormViewDialog, {
            resModel: 'social.stream',
            context: {
                default_media_id: parseInt(target.dataset.mediaId),
                default_account_id: parseInt(target.dataset.accountId),
                form_view_ref: 'social.social_stream_view_form_wizard',
            },
            onRecordSaved: (result) => this.props.onSaved(result),
        });
        this.props.close();
    }

    async _onClickSocialMedia(mediaId, context) {
        const selectCompany = this.modalRef().querySelector('select[name="company_id"]');
        const companyId = selectCompany ? parseInt(selectCompany.value) || 0 : undefined;
        const action = await this.orm.call("social.media", "action_add_account", [mediaId], {
            company_id: companyId,
            context,
        });
        this.action.doAction(action);
    }

    get medias() {
        return this.props.socialMedia;
    }

    /**
     * Remove the given social account.
     */
    async _onDeleteAccount(accountId) {
        this.addDialog(ConfirmationDialog, {
            body: _t("Are you sure you want to delete this account?"),
            confirm: async () => {
                await this.orm.call("social.account", "unlink", [accountId]);
                window.location.reload();
            },
            cancel: () => {},
        });
    }
}
