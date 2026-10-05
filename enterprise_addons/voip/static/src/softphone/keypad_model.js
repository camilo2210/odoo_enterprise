export class KeypadModel {
    input = {
        value: "",
        selection: {
            start: 0,
            end: 0,
            direction: "none",
        },
        focus: false,
        /** @type {import("@mail/core/country_model").Country | null} */
        country: null,
        isValid: false,
    };
    showMore = false;
    /**
     * Used by the Dialer only.
     * @type {{resModel: string, resId: number, partnerId?: number}|null}
     */
    prefillContext = null;

    constructor({ value = "" } = {}) {
        this.value = value;
    }

    reset() {
        Object.assign(this, new KeypadModel());
    }
}
