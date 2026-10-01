import { Component, t, useProps } from "@odoo/owl";
import { AddressBook } from "@voip/softphone/address_book";
import { Dialer } from "@voip/softphone/dialer";

export class AddCallView extends Component {
    static components = { AddressBook, Dialer };
    static template = "voip.AddCallView";

    props = useProps({
        contactExcludeFilter: t.function(),
        onClickBack: t.function(),
        state: t.object(),
    });
}
