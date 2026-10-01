import { untrack, useEffect, useListener } from "@odoo/owl";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_utils";

/**
 * @param {{
 *  inputRef: import("@odoo/owl").Signal<HTMLInputElement | null>
 *  invalid: import("@odoo/owl").Signal<boolean>;
 *  value: import("@odoo/owl").Signal<string>;
 *  discard: () => any;
 *  onChange: (value: number) => any;
 *  onCommit: () => any;
 *  onKeyDown: (ev: KeyboardEvent) => any;
 *  parse: (formattedValue: string) => number;
 * }} params
 */
export function useInputHook(params) {
    /**
     * Roughly the same as onChange, but called at more specific / critical times. (See bus events)
     */
    async function commitChanges(urgent) {
        if (!inputRef()) {
            return;
        }

        isDirty = inputRef().value !== lastSetValue;
        if (isDirty || urgent) {
            let isInvalid = false;
            isDirty = false;
            const strValue = inputRef().value;
            let val;
            if (params.parse) {
                try {
                    val = params.parse(strValue);
                } catch {
                    isInvalid = true;
                    if (urgent) {
                        return;
                    } else {
                        params.invalid.set(true);
                    }
                }
            }

            if (isInvalid) {
                return;
            }

            const result = params.onCommit(val); // means change has been committed
            if (result) {
                lastSetValue = inputRef().value;
                params.invalid.set(false);
            }
        }
    }

    /**
     * When a user types, we need to set the field as dirty.
     *
     * @param {InputEvent & { currentTarget: HTMLInputElement }} ev
     */
    function onInput(ev) {
        isDirty = ev.currentTarget.value !== lastSetValue;
        params.invalid.set(false);
    }

    /**
     * On blur, we consider the field no longer dirty, even if it were to be invalid.
     * However, if the field is invalid, the new value will not be committed to the model.
     *
     * @param {Event & { currentTarget: HTMLInputElement }} ev
     */
    function onChange(ev) {
        if (isDirty) {
            isDirty = false;
            let isInvalid = false;
            let val = ev.currentTarget.value;
            try {
                val = params.parse(val);
            } catch {
                params.invalid.set(true);
                isInvalid = true;
            }

            if (!isInvalid) {
                params.onChange(val);
                lastSetValue = ev.currentTarget.value;
            }

            params.invalid.set(false);
        }
    }

    /**
     * @param {KeyboardEvent & { currentTarget: HTMLInputElement }} ev
     */
    function onKeydown(ev) {
        const hotkey = getActiveHotkey(ev);
        if (hotkey === "escape") {
            params.discard();
        } else if (["enter", "tab", "shift+tab"].includes(hotkey)) {
            commitChanges();
        }
        params.onKeyDown(ev);
    }

    const inputRef = params.inputRef;

    /*
     * A field is dirty if it is no longer sync with the model
     * More specifically, a field is no longer dirty after it has *tried* to update the value in the model.
     * An invalid value will therefore not be dirty even if the model will not actually store the invalid value.
     */
    let isDirty = false;

    /**
     * The last value that has been committed to the model.
     * Not changed in case of invalid field value.
     */
    let lastSetValue = null;

    useListener(inputRef, "input", onInput);
    useListener(inputRef, "change", onChange);
    useListener(inputRef, "keydown", onKeydown);

    /**
     * Sometimes, a patch can happen with possible a new value for the field
     * If the user was typing a new value (isDirty) or the field is still invalid,
     * we need to do nothing.
     * If it is not such a case, we update the field with the new value.
     */
    useEffect(() => {
        const isInvalid = untrack(params.invalid) ?? false;
        const value = untrack(params.value);
        if (inputRef() && !isDirty && !isInvalid) {
            inputRef().value = value;
            lastSetValue = value;
        }
    });
}
