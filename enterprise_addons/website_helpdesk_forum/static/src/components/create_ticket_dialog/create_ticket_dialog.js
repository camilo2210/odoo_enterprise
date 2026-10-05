import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, markup, proxy, signal, t, useProps } from "@odoo/owl";

export class CreateTicketDialog extends Component {
    static template = "website_helpdesk_forum.CreateTicketDialog";
    static components = { Dialog };

    props = useProps({
        forumId: t.number(),
        postId: t.number(),
        close: t.function().optional(),
    });

    inputTextRef = signal.ref();

    setup() {
        this.state = proxy({});
        this.notification = useService("notification");
        this.orm = useService("orm");

        onWillStart(async () => {
            const forumPostData = await rpc(window.location.href + "/get-forum-data");
            this.state.data = {
                ...forumPostData,
                team_id: forumPostData.teams?.[0]?.[0],
            };
        });
    }

    _createTicket() {
        return this.orm.call("forum.forum", "create_ticket", [
            this.props.forumId,
            this.props.postId,
            this.state.data,
        ]);
    }

    _checkInputIsValid() {
        const isValid = this.inputTextRef().value.trim().length;
        this.inputTextRef().classList.toggle("is-invalid", !isValid);
        return isValid;
    }

    async onCreateTicket() {
        if (!this._checkInputIsValid()) {
            return;
        }
        const response = await this._createTicket();
        const message = _t(
            "Helpdesk ticket %(ticket)s has been successfully created for this forum post.",
            { ticket: markup`<b>#${response.ticket}</b>` }
        );
        this.notification.add(message, { type: "success" });
        this.props.close();
    }

    async onCreateAndViewTicket() {
        if (!this._checkInputIsValid()) {
            return;
        }
        const response = await this._createTicket();
        window.open(response.url, "_blank");
        this.props.close();
    }
}
