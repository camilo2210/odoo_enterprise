import { Record } from "@mail/model/export";

export class PlanningRole extends Record {
    static _name = "planning.role";

    /** @type {number} */
    id;
    /** @type {string} */
    color;
    /** @type {string} */
    name;
}

PlanningRole.register();
