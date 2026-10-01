import { Composer } from "@mail/core/common/composer";
import { AccountReportController } from "@account_reports/components/account_report/controller";
import { serializeDate } from "@web/core/l10n/dates";

import { t, useProps } from "@odoo/owl";
const { DateTime } = luxon;

export class AccountReportComposer extends Composer {
    setup() {
        super.setup(...arguments);
        this.accountReportProps = useProps({
            date_to: t.string(),
            list: t.any().optional(),
            reportController: t.instanceOf(AccountReportController).optional(),
        });
    }

    get postData() {
        return {
            ...super.postData,
            account_reports_annotation_date: serializeDate(
                DateTime.fromISO(this.accountReportProps.date_to)
            ),
        };
    }

    async _sendMessage(value, postData, extraData) {
        const message = await super._sendMessage(value, postData, extraData);
        this.accountReportProps.reportController?.addAnnotation(
            message.id,
            message.model,
            message.res_id,
        );
        this.accountReportProps.list?.records.forEach((record) => {
            if (record.isInEdition) {
                record.load();
            }
        });
        return message;
    }

    get fullComposerAdditionalContext() {
        return {
            ...super.fullComposerAdditionalContext,
            default_account_reports_annotation_date: serializeDate(
                DateTime.fromISO(this.accountReportProps.date_to)
            ),
        };
    }
}
