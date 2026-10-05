import { useService } from "@web/core/utils/hooks";
import { Record } from "@web/model/record";
import { Field, getFieldFromRegistry } from "@web/views/fields/field";
import { _t } from "@web/core/l10n/translation";

import {
    Component,
    onWillStart,
    useSubEnv,
    proxy,
    signal,
    t,
    useEffect,
    useProps,
} from "@odoo/owl";

export class TimesheetInlineForm extends Component {
    static components = {
        Record,
        Field,
    };
    static template = "timesheet_grid.TimesheetInlineForm";

    props = useProps({
        data: t.object().optional(),
        context: t.object().optional(),
        onSaveCallback: t.function().optional(),
        onWriteTimesheet: t.function().optional(),
        onDelete: t.function().optional(),
        saveButtonText: t.string().optional(),
        onDiscard: t.function(),
        onRecordReady: t.function().optional(),
        onLinkedRecordSaved: t.function().optional(),
    });
    descriptionFieldRef = signal.ref();

    setup() {
        this.notificationService = useService("notification");
        this.staticTimerService = useService("static_timesheet_timer");
        this.orm = useService("orm");
        this.uiService = useService("ui");
        this.state = proxy({
            disabledButtons: false,
        });

        this.model = "account.analytic.line";
        this.currentRecord = null;

        useEffect(() => {
            void this.props.data; // subscribe to data prop changes
            const el = this.descriptionFieldRef();
            if (el) {
                el.querySelector("textarea").focus();
            }
        });

        onWillStart(this.onWillStart);
        useSubEnv({
            inDialog: true,
            onLinkedTaskRecordSaved: () => this.props.onLinkedRecordSaved?.(),
        });
        this.recordHooks = {
            onRootLoaded: (record) => {
                this.onRecordReady(record);
            },
        };
    }

    async onWillStart() {
        // we need the empty method to patch it in sale_timesheet_enterprise
    }

    onRecordReady(record) {
        this.currentRecord = record;
        if (this.props.onRecordReady) {
            this.props.onRecordReady(record);
        }
    }

    async onSave(record) {
        if (this.state.disabledButtons) {
            return false;
        }
        this.state.disabledButtons = true;
        const timesheetData = await this._saveTimesheet(record);
        if (timesheetData) {
            const timesheet = {
                ...record,
                data: timesheetData,
            };
            this.currentRecord = null;
            if (this.props.data?.id && this.props.onWriteTimesheet) {
                this.props.onWriteTimesheet(timesheet);
            } else if (this.props.onSaveCallback) {
                this.props.onSaveCallback(timesheet, timesheetData);
            }
            this.state.disabledButtons = false;
            return true;
        }
        this.state.disabledButtons = false;
        return false;
    }

    async _saveTimesheet(record) {
        if (await record.save()) {
            return record.data;
        }
        return null;
    }

    async onDiscard(record) {
        await record.discard();
        this.currentRecord = null;
        this.props.onDiscard(record);
    }

    async onDelete(record) {
        const resId = record.resId;
        if ((await record.delete()) === false) {
            return false;
        }
        if (this.props.onDelete) {
            this.props.onDelete(resId);
        }
        return true;
    }

    isFormEdited(record) {
        return record.dirty;
    }

    async onKeydown(ev, record) {
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            ev.stopPropagation();
            ev.preventDefault();
            await this.onSave(record);
        }
    }

    get fieldNames() {
        return [
            "id",
            "date",
            "user_id",
            "name",
            "project_id",
            "task_id",
            "company_id",
            "unit_amount",
        ];
    }

    get isMobile() {
        return this.uiService.isSmall;
    }

    get activeFields() {
        const activeFields = {};
        for (const fieldName of this.fieldNames) {
            activeFields[fieldName] = this.staticTimerService.getTimesheetTimerFieldInfo(fieldName);
        }
        activeFields.project_id.placeholder = "";
        activeFields.task_id.placeholder = "";
        if (this.props.onLinkedRecordSaved) {
            activeFields.task_id.field = getFieldFromRegistry(
                activeFields.task_id.type,
                "aw_task_with_hours"
            );
        }
        return activeFields;
    }

    get saveButtonText() {
        return this.props.saveButtonText;
    }

    get discardButtonText() {
        return _t("Discard");
    }

    get recordData() {
        return this.props.data;
    }
}
