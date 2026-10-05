import { CalendarController } from "@web/views/calendar/calendar_controller";


export class AccountReturnCalendarController extends CalendarController {

    async editRecord(record, context) {
        const action = await this.orm.call("account.return", "action_open_account_return", [record.id]);
        if (!action)
            return
        return this.action.doAction(action);
    }
}
