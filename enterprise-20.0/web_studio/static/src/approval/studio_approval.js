import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { StudioApprovalInfos } from "@web_studio/approval/approval_infos";
import { Component, onWillUnmount, signal, t, useProps } from "@odoo/owl";

function useOpenExternal() {
    const closeFns = [];
    function open(_open) {
        const close = _open();
        closeFns.push(close);
        return close;
    }

    onWillUnmount(() => {
        closeFns.forEach((cb) => cb());
    });
    return open;
}

export class StudioApproval extends Component {
    static template = "StudioApproval";
    props = useProps({
        approval: t.object(),
    });

    rootRef = signal.ref();

    setup() {
        this.dialog = useService("dialog");
        this.uiService = useService("ui");
        this.popover = usePopover(StudioApprovalInfos);
        this.openExternal = useOpenExternal();
    }

    get approval() {
        return this.props.approval;
    }

    get state() {
        return this.approval.state;
    }

    toggleApprovalInfo() {
        if (this.approval.isAppovalBlockedByParentRule()) {
            return;
        }
        if (this.uiService.isSmall) {
            if (this.isOpened) {
                this.closeInfos();
                this.closeInfos = null;
                return;
            }
            const onClose = () => {
                this.isOpened = false;
            };
            this.closeInfos = this.openExternal(() =>
                this.dialog.add(
                    StudioApprovalInfos,
                    { approval: this.approval, isPopover: false },
                    { onClose }
                )
            );
        } else {
            this.popover.open(this.rootRef(), { approval: this.approval, isPopover: true });
        }
    }

    getEntry(ruleId) {
        return this.state.entries.find((e) => e.rule_id[0] === ruleId);
    }
}
