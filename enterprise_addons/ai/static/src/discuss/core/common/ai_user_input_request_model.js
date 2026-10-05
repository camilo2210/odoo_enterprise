import { Record, fields } from "@mail/model/export";

export class AiUserInputRequest extends Record {
    static _name = "ai.user.input.request";
    static id = "ai_session_id";

    ai_session_id = fields.One("ai.session", { inverse: "userInputRequest" });
    /** @type {"question" | "confirmation"} */
    type = "";
    body = fields.Html("");
    multiSelect = false;
    allowFreeText = false;
    /** @type {Array<{label: string, value: string}>} */
    choices = [];
    resumeToken = undefined;
}

AiUserInputRequest.register();
