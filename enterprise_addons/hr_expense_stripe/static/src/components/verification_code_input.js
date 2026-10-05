import { Component, Resource, t, useProps } from "@odoo/owl";

export class InputVerificationCode extends Component {
    static template = "hr_expense_stripe.InputVerificationCode";

    props = useProps({
        nbInputs: t.number(),
        onValidatedInput: t.function().optional(),
    });

    inputRefs = new Resource({ name: "inputs" });

    get inputs() {
        return this.inputRefs.items();
    }

    onFocus(ev) {
        const input_el = ev.target;
        input_el.setSelectionRange(0, input_el.value.length);
    }

    onInput(ev) {
        if (this.verificationCode.length === this.props.nbInputs && this.props.onValidatedInput) {
            this.props.onValidatedInput(this.verificationCode);
        }

        const i = this.getInputRefIndex(ev.target);
        if (i < this.props.nbInputs - 1 && ev.target.value.length === 1) {
            this.inputs[i + 1].focus();
        }
    }

    onPaste(ev) {
        if (!ev.clipboardData?.items) {
            return;
        }

        ev.preventDefault();

        const pastedData = ev.clipboardData.getData("text").split("");
        const start_index = this.getInputRefIndex(ev.target);
        for (const inputEl of this.inputs.slice(start_index)) {
            inputEl.value = pastedData.shift() || "";
            this.onInput({ target: inputEl });
        }
    }

    onKeydown(ev) {
        const i = this.getInputRefIndex(ev.target);
        if (ev.key === "Backspace" && ev.target.value === "" && i > 0) {
            ev.preventDefault();
            const newFocusedEl = this.inputs[i - 1];
            newFocusedEl.focus();
            newFocusedEl.value = "";
        } else if (ev.key === "ArrowLeft") {
            ev.preventDefault();
            const indexToFocus = i > 0 ? i - 1 : 0;
            this.inputs[indexToFocus].focus();
        } else if (ev.key === "ArrowRight") {
            ev.preventDefault();
            const indexToFocus = i < this.props.nbInputs - 1 ? i + 1 : i;
            this.inputs[indexToFocus].focus();
        }
    }

    get verificationCode() {
        let verificationCode = "";

        for (const input of this.inputs) {
            const value = input.value;
            if (value) {
                verificationCode += value;
            }
        }

        return verificationCode;
    }

    getInputRefIndex(el) {
        return this.inputs.findIndex((inputEl) => inputEl == el);
    }
}
