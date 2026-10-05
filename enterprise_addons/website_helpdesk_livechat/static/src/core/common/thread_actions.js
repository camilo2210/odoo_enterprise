import { registerThreadAction } from "@mail/core/common/thread_actions";
import "@mail/discuss/call/common/thread_actions";
import { attClassObjectToString } from "@mail/utils/common/format";

import { LivechatCommandDialog } from "@im_livechat/core/common/livechat_command_dialog";

import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";

registerThreadAction("create-ticket", {
    actionPanelComponent: LivechatCommandDialog,
    actionPanelComponentProps: ({ thread }) => ({
        commandName: "ticket",
        placeholderText: _t("e.g. Product arrived damaged"),
        thread,
        title: _t("Create Ticket"),
        icon: "support",
    }),
    actionPanelOpen({ rootRef }) {
        this.popover?.open(
            rootRef().querySelector(`[name="${this.id}"]`),
            this.actionPanelComponentProps
        );
    },
    actionPanelOuterClass: ({ owner, store }) =>
        attClassObjectToString({
            [store.discussDropdownMenuClass(owner)]: !owner.env.inMeetingView,
        }),
    condition: false, // managed by ThreadAction patch
    icon: "support",
    name: _t("Create Ticket"),
    sequence: 15,
    sequenceGroup: 25,
    setup({ owner }) {
        if (!owner.env.inChatWindow) {
            this.popover = usePopover(LivechatCommandDialog, {
                onClose: () => this.actionPanelClose(),
                popoverClass: this.actionPanelOuterClass,
            });
        }
    },
});
