import { useBus } from "@web/core/utils/hooks";
import { isNull } from "@web/views/utils";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import {AccountReturnKanbanRecord} from "./account_return_kanban_record";
import { AccountReturnBaseKanbanRenderer } from "./account_return_base_kanban_renderer";
import { useDeleteRecords } from "@web/views/view_hook";
import { usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";
import { GlobalBusPlugin } from "@web/core/global_bus_plugin";


/**
 * Focus the previous/next card, treating every card of the area as a flat list.
 *
 * The account return kanban templates lay their cards out in a single column and
 * don't render the `.o_kanban_group` elements the standard
 * `KanbanRenderer.focusNextCard` relies on, hence this flat implementation.
 * Only up/down navigation is supported.
 *
 * @param {HTMLElement} area
 * @param {"down"|"up"|"right"|"left"} direction
 * @returns {true|undefined} true if the next card has been focused
 */
export function focusNextFlatCard(area, direction) {
    if (direction !== "up" && direction !== "down") {
        return;
    }
    const closestCard = document.activeElement.closest(".o_kanban_record");
    if (!closestCard) {
        return;
    }
    const cards = [...area.querySelectorAll(".o_kanban_record")];
    const iCard = cards.indexOf(closestCard);
    if (iCard === -1) {
        return;
    }
    const nextCard = cards[direction === "down" ? iCard + 1 : iCard - 1];

    if (nextCard) {
        nextCard.focus();
        return true;
    }
}


export class AccountReturnKanbanRenderer extends AccountReturnBaseKanbanRenderer {
    static template="account_reports.account_return_kanban_renderer";

    static components = {
        ...KanbanRenderer.components,
        AccountReturnKanbanRecord
    };

    orm = usePlugin(ORM);
    actionPlugin = usePlugin(ActionPlugin);

    setup() {
        super.setup();
        this.deleteRecordsWithConfirmation = useDeleteRecords(this.props.list.model);

        useBus(usePlugin(GlobalBusPlugin).bus, "return_reload_model", (ev) => {
            const recordIds = ev.detail.resIds;
            let recordToReload = this.records.filter((record) => recordIds.includes(record.resId));
            for (let record of recordToReload) {
                record.model.load();
            }
        });
    }

    deleteRecord(record) {
        this.deleteRecordsWithConfirmation({}, [record]);
    }

    focusNextCard(area, direction) {
        return focusNextFlatCard(area, direction);
    }

    async openRecord(record, params) {
        if (record.context?.in_checks_view) {
            return
        }
        const action = await this.orm.call("account.return", "action_open_account_return", [record.resIds]);
        if (!action)
            return
        return this.actionPlugin.doAction(action);
    }

    get records() {
        const { list } = this.props;
        if (list.isGrouped) {
            return list.groups.flatMap((group) => group.list.records);
        }
        else {
            return list.records;
        }
    }

    get maxStateCount() {
        return Math.max(1, ...this.records.map(r => r.data.visible_states.length));
    }

    get groups() {
        const { list } = this.props;
        if (!list.isGrouped) {
            return false;
        }

        return list.groups.map((group, i) => ({
            ...group,
            key: isNull(group.value) ? `group_key_${i}` : String(group.value),
        }));
    }
}
