import { Record } from "@mail/model/export";

export class AIPromptButton extends Record {
    static _name = "ai.prompt.button";

    /** @type {number} */
    id;
    /** @type {string} */
    name;
    /** @type {string|undefined} */
    prompt;
    /** @type {number|undefined} */
    sequence;
}

AIPromptButton.register();
