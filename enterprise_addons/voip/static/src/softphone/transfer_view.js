import { Component, t, useProps } from "@odoo/owl";
import { Session } from "@voip/core/web/session";
import { ActionButton } from "@voip/softphone/action_button";
import { AddressBook } from "@voip/softphone/address_book";
import { Keypad } from "@voip/softphone/keypad";
import { useService } from "@web/core/utils/hooks";

export class TransferView extends Component {
    static components = { ActionButton, AddressBook, Keypad };
    static template = "voip.TransferView";

    props = useProps({
        contactExcludeFilter: t.function(),
        frontSession: t.instanceOf(Session),
        onClickBack: t.function(),
        onClickTransferContact: t.function(),
        onClickTransferPhone: t.function(),
        state: t.object(),
    });

    setup() {
        const store = useService("mail.store");
        this.props.state.keypad.input.value ||=
            store.self_user.res_users_settings_id.external_device_number || "";
    }
}
