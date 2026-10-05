import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, proxy, t, useListener, useProps } from "@odoo/owl";

export class SignItemCustomPopover extends Component {
    static template = "sign.SignItemCustomPopover";
    static components = {};

    props = useProps({
        id: t.number(),
        alignment: t.string(),
        header_title: t.string(),
        placeholder: t.string(),
        required: t.boolean(),
        constant: t.boolean(),
        option_ids: t.array(),
        onValidate: t.function(),
        type: t.string(),
        onDelete: t.function(),
        onDuplicate: t.function(),
        onClose: t.function(),
        debug: t.string(),
        close: t.function(),
        onCopyItem: t.function(),
        num_options: t.number().optional(),
        radio_set_id: t.number().optional(),
    });

    setup() {
        this.alignmentOptions = [
            { title: _t("Left"), key: "left" },
            { title: _t("Center"), key: "center" },
            { title: _t("Right"), key: "right" },
        ];
        this.state = proxy({
            alignment: this.props.alignment,
            placeholder: this.props.placeholder,
            constant: this.props.constant,
            required: this.props.required,
            option_ids: this.props.option_ids,
            num_options: this.props.num_options,
            radio_set_id: this.props.radio_set_id,
            selectionOptionsText: "",
        });
        this.orm = useService("orm");
        onWillStart(async () => {
            const options = await this.orm.searchRead("sign.item.option", [
                ["id", "in", this.props.option_ids],
            ]);
            this.state.selectionOptionsText = options.map((option) => option.value).join("\n");
        });

        this.isMounted = false;
        /**
         * Focuses the selection options textarea when the popover is rendered
         */
        onMounted(() => {
            if (this.props.type === "selection") {
                const textarea = document.querySelector(".o_sign_selection_input_option textarea");
                if (textarea) {
                    textarea.focus();
                }
            }
            this.isMounted = true;
        });

        this.notification = useService("notification");
        this.typesWithAlignment = new Set(["text", "textarea", "date"]);
        useListener(window, "keydown", this.onGlobalKeyDown.bind(this), { capture: true });
    }

    onGlobalKeyDown(event) {
        if (!this.isMounted) {
            return;
        }
        if (event.key == "c" && (event.ctrlKey || event.metaKey)) {
            this.notification.add("Sign Item Copied", { type: "success" });
            this.props.onCopyItem(this.props.id);
        } else if (event.key == "Delete") {
            this.props.onDelete();
        }
    }

    handleNumOptionsChange(value) {
        if (Number(value) < 2) {
            return;
        }
        this.state["num_options"] = Number(value);
    }

    onChange(key, value) {
        this.state[key] = value;

        // Focuses the placeholder input if the item is set as read-only
        if (key === "constant") {
            if (value) {
                document.querySelector("#o_sign_name")?.focus();
            } else {
                this.state.placeholder = this.props.placeholder;
            }
        }
    }

    async onValidate() {
        if (this.props.type === "selection" && !this.state.selectionOptionsText) {
            this.notification.add(
                _t("Selection field cannot be empty. Please add at least one option."),
                {
                    type: "warning",
                }
            );
            return;
        }

        const options = this.state.selectionOptionsText
            .split("\n")
            .map((opt) => opt.trim())
            .filter((opt) => opt);
        this.state.option_ids = await this.orm.call(
            "sign.item.option",
            "get_selection_ids_from_value",
            [null, options]
        );
        this.props.onValidate(this.state);
    }

    get showAlignment() {
        return this.typesWithAlignment.has(this.props.type);
    }

    onChangeSelectionOptions(value) {
        this.state.selectionOptionsText = value;
    }
}
