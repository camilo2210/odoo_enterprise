import { KanbanRecord } from "@web/views/kanban/kanban_record";

export class AccountReturnKanbanRecord extends KanbanRecord {
    setup() {
        super.setup();
        if (this.props.record.data.activity_type_icon === 'check') {
            this.props.record.data.activity_type_icon = 'checklist';
        }
    }

    getCardClasses() {
        let classes = super.getCardClasses();
        // Remove the cursor on the card of the return when being on the checks kanban view
        if (this.props.record.context?.in_checks_view) {
            classes = classes.replace(/\bcursor-pointer\b/, "");
        }
        else {
            if (this.props.record.data.is_completed) {
                classes += " _o_left_border_success";
            }
            else if (this.props.record.data.days_to_deadline < 0) {
                classes += " _o_left_border_danger";
            }
            else if(this.props.record.data.days_to_deadline <= 7) {
                classes += " _o_left_border_warning";
            }
        }

        return classes;
    }
}
