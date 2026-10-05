import { Component, signal, t, useProps } from "@odoo/owl";

import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class CallMethodSelectionDialog extends Component {
    static components = { Dialog };
    static template = "voip.CallMethodSelectionDialog";

    props = useProps({
        close: t.function(),
        setVoipChoice: t.function(),
    });

    fieldsetRef = signal.ref();
    rememberCheckboxRef = signal.ref();

    setup() {
        this.store = useService("mail.store");
        this.orm = useService("orm");
    }

    get dialogProps() {
        return { title: _t("Select a call method") };
    }

    /** @param {MouseEvent} ev */
    onClickConfirm(ev) {
        const checkedRadio = this.fieldsetRef().querySelector(
            "input[type='radio'][name='call-method']:checked"
        );
        if (!checkedRadio) {
            return;
        }
        const { value } = checkedRadio;
        if (this.rememberCheckboxRef().checked) {
            this.orm.call(
                "res.users.settings",
                "set_res_users_settings",
                [[this.store.self_user.res_users_settings_id.id]],
                {
                    new_settings: { how_to_call_on_mobile: value },
                }
            );
        }
        this.props.setVoipChoice(value === "voip");
        this.props.close();
    }
}
