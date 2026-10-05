import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { ORM } from "@web/core/orm_plugin";
import { UIPlugin } from "@web/core/ui/ui_plugin";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

import { Component, computed, t, usePlugin, useProps } from "@odoo/owl";

import { parseLineId } from "@account_reports/js/util";
import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReviewStateSelectionBadge } from "@account/components/account_review_state_selection/account_review_state_selection_badge";


export class AccountReportLineName extends Component {
    static template = "account_reports.AccountReportLineName";
    static components = {
        Dropdown,
        DropdownItem,
        AccountReviewStateSelectionBadge,
    };
    props = useProps({
        lineIndex: t.signal(t.number()),
        line: t.object(),
    });

    action = usePlugin(ActionPlugin);
    controller = usePlugin(AccountReportController);
    orm = usePlugin(ORM);
    ui = usePlugin(UIPlugin);
    
    isLoadMore = computed(() => this.controller.isLoadMoreLine(this.props.line.id()));
    isChatterAnnotated = computed(() => Boolean(this.props.line.visible_annotations?.()));
    isChatterSelected = computed(() => this.props.line.id() === this.controller.chatterState.lineId());

    hasAction = computed(() => Boolean(this.props.line.action_id?.()));
    hasCaretOptions = computed(() => this.caretOptions?.length > 0);
    hasAccountStatus = computed(() => Boolean(this.props.line.account_status?.id()));
    hasChatter = computed(() => Boolean(this.props.line.chatter?.model()));

    modelName = computed(() => parseLineId(this.props.line.id()).at(-1)[1]);

    get accountStatusBadgeOptions() {
        return {
            todo: { decoration: "info" },
            reviewed: { decoration: "success" },
            supervised: { decoration: "success" },
            anomaly: { decoration: "danger" },
        };
    }

    onAccountStatusChange(value) {
        if (this.props.line.account_status?.status) {
            this.props.line.account_status.status.set(value);
        }
    }

    //------------------------------------------------------------------------------------------------------------------
    // Caret options
    //------------------------------------------------------------------------------------------------------------------
    get caretOptions() {
        if (!this.controller.data()) return [];
        return this.controller.caretOptions[this.props.line.caret_options?.()];
    }

    async caretAction(caretOption) {
        const res = await this.orm.call(
            "account.report",
            "dispatch_report_action",
            [
                this.controller.options().report_id,
                this.controller.options(),
                caretOption.action,
                {
                    line_id: this.props.line.id(),
                    action_param: caretOption.action_param,
                },
            ],
            {
                context: this.controller.context,
            },
        );

        return this.action.doAction(res);
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Classes
    // -----------------------------------------------------------------------------------------------------------------
    get lineNameClasses() {
        const line = this.props.line;
        let classes = "text";

        if (line.unfoldable?.())
            classes += " unfoldable";

        if (line.is_draft?.())
            classes += " draft";

        if (line.css_class?.())
            classes += ` ${ line.css_class() }`;

        return classes;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Action
    // -----------------------------------------------------------------------------------------------------------------
    async triggerAction() {
        const res = await this.orm.call(
            "account.report",
            "execute_action",
            [
                this.controller.options().report_id,
                this.controller.options(),
                {
                    id: this.props.line.id(),
                    actionId: this.props.line.action_id?.(),
                },
            ],
            {
                context: this.controller.context,
            },
        );

        return this.action.doAction(res);
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Load more
    // -----------------------------------------------------------------------------------------------------------------
    async loadMore() {
        const linesByParent = {};
        for (const line of this.controller.lines) {
            if (!line['parent_id']) continue;
            (linesByParent[line['parent_id']] ??= []).push(line);
        }

        const lineToExpandId = this.props.line.parent_id?.();
        const alreadyLoadedChildLineIds = this.retrieveAllLoadedChildLines(linesByParent, lineToExpandId).map(l => l.id);

        const newLines = await this.orm.call(
            "account.report",
            this.controller.options().readonly_query ? "get_expanded_lines_readonly" : "get_expanded_lines",
            [
                this.controller.options().report_id,
                this.controller.options(),
                lineToExpandId,
                this.props.line.groupby?.(),
                this.props.line.expand_function?.(),
                this.props.line.horizontal_split_side?.(),
                this.controller._retrieve_line_comparison_base_value(),
                true,
                alreadyLoadedChildLineIds, // So that we avoid recomputing uselessly groupby of already unfolded and loaded lines
            ],
        );

        this.controller.setLineVisibility(newLines);

        // Insert the new lines at the right positions, keeping the result of previously unfolded lines
        const linesToInsert = [];
        for (const newLine of newLines) {
            linesToInsert.push(newLine);
            linesToInsert.push(...this.retrieveAllLoadedChildLines(linesByParent, newLine['id']));
        }

        let parentIndex = null;
        const lines = this.controller.lines;
        for (let i = this.props.lineIndex() - 1; i >= 0; i--){
            if (lines[i].id === lineToExpandId) {
                parentIndex = i;
                break;
            }
        }
        const nberLinesToRemove = this.props.lineIndex() - parentIndex;
        
        // Sorting is done before inserting the lines, so that linesOrder is properly set on the controller before triggering a UI refresh.
        if (this.controller.areLinesOrdered()) {
            const newLinesOrder = await this.controller.loadLinesOrder(linesToInsert);
            const linesOrder = this.controller.linesOrder();

            // Modify the indices of the sublines so that they come all just after their parent's
            for (let i = 0 ; i < newLinesOrder.length ; i++) {
                newLinesOrder[i] += parentIndex + 1;
            }

            // Modify all indices stored in linesOrder for lines which will come after parent once the lines have been inserted
            let parentLineOrderIndex;
            for (let i = 0 ; i < linesOrder.length ; i++) {
                if (linesOrder[i] === parentIndex) {
                    parentLineOrderIndex = i;
                }
                else if (linesOrder[i] > parentIndex) {
                    linesOrder[i] += newLinesOrder.length - nberLinesToRemove;
                }
            }

            // Remove elements that would already be present in linesOrder before injecting the order of unfolded lines
            const reloadedIndices = new Set(newLinesOrder);
            const kept = linesOrder.filter(x => !reloadedIndices.has(x));
            kept.splice(parentLineOrderIndex + 1, 0, ...newLinesOrder);
            linesOrder.length = 0;
            linesOrder.push(...kept);
        }
        else {
            // Reset linesOrder to use the indices of the lines directly, making sure it stays consistent with the newly loaded lines
            this.controller.linesOrder.set(null);
        }

        // Insert lines, refreshing the UI
        this.controller.insertLines(parentIndex + 1, nberLinesToRemove, linesToInsert);
    }

    retrieveAllLoadedChildLines(linesByParent, lineId) {
        const rslt = [];
        if (lineId in linesByParent) {
            for (const childLine of linesByParent[lineId]) {
                rslt.push(childLine);
                rslt.push(...this.retrieveAllLoadedChildLines(linesByParent, childLine['id']));
            }
        }
        return rslt;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Fold / Unfold
    // -----------------------------------------------------------------------------------------------------------------
    toggleFoldable() {
        if (!this.props.line.unfoldable?.()) return;

        if (this.props.line.unfolded())
            this.controller.foldLine(this.props.lineIndex());
        else
            this.controller.unfoldLine(this.props.lineIndex());
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Chatter
    // -----------------------------------------------------------------------------------------------------------------
    async openChatter(ev) {
        ev.stopPropagation();
        if (!this.props.line.chatter?.id()) return;

        this.controller.toggleLineChatter({
            resModel: this.props.line.chatter.model(),
            resId: this.props.line.chatter.id(),
            lineId: this.props.line.id(),
        });
    }
}

registry.category("account_reports.default_components").add("AccountReportLineName", AccountReportLineName);
