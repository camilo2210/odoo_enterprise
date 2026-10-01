import { Component, proxy, t, useProps } from "@odoo/owl";
import { KeepLast } from "@web/core/utils/concurrency";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { debounce } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { HrContractSalarySelectMenu } from "../js/hr_contract_salary_select_menu";

class SelectMenuWrapper extends Component {
    static template = "hr_contract_salary.SelectMenuWrapper";
    static components = { HrContractSalarySelectMenu };

    props = useProps({
        el: t.object(),
        name: t.string(),
        selectMenus: t.object(),
    });

    setup() {
        this.selectMenu = proxy(this.props.selectMenus[this.props.name]);

        let optgroup = [...this.props.el.querySelectorAll("optgroup")]
        if (optgroup.length){
            this.selectMenu.groups = optgroup.map(x => ({
                label: x.label,
                choices: [...x.querySelectorAll("option")],
            }));
        } else {
            this.selectMenu.choices = [...this.props.el.querySelectorAll("option")].filter((x) => x.value);
        }

        this.props.el.classList.add("d-none");

    }

    onSelect(value) {
        this.selectMenu.value = value;
        this.props.el.value = value;
        // Manually trigger the change event
        const event = new Event("change", { bubbles: true });
        this.props.el.dispatchEvent(event);
    }
}

export class SalaryPackage extends Interaction {
    static selector = "#hr_cs_form";

    dynamicContent = {
        ".benefit_input": {
            "t-on-change": this.onchangeBenefit,
        },
        "input.folded": {
            "t-on-change": this.onchangeFolded,
        },
        ".personal_info": {
            "t-on-change": this.onchangePersonalInfo,
        },
        "#hr_cs_submit": {
            "t-on-click": this.submitSalaryPackage,
        },
        ".o_submit_feedback": {
            "t-on-click": this.submitFeedback,
        },
        "a[name='recompute']": {
            "t-on-click": this.recompute,
        },
        "button[name='toggle_personal_information']": {
            "t-on-click": this.togglePersonalInformation,
        },
        "input.border-danger": {
            "t-on-change": this.clearFieldError,
        },
        "div.invalid_radio": {
            "t-on-change": this.clearRadioError,
        },
        "input.document": {
            "t-on-change": this.onchangeDocument,
        },
        "input[type='range']": {
            "t-on-input": this.onchangeSlider,
        },
        "select[name='private_country_id']": {
            "t-on-change": this.onchangeCountry,
        },
        "select:required": {
            "t-on-change": this.clearSelectError,
        },
        "#hr_contract_salary *:has(> select:not(.refuse-reason-select))": {
            "t-component": (el) => {
                const childEl = el.querySelector("select:not(.refuse-reason-select)");
                return [
                    SelectMenuWrapper,
                    {
                        el: childEl,
                        name: childEl.name,
                        selectMenus: this.selectMenus,
                    },
                ];
            },
        },
        "input[type='number']": {
            "t-on-keydown": this.onkeydownInput,
        },
        
    };

    setup() {
        this.keepLast = new KeepLast();
        this.selectMenus = proxy({});
        document.body.setAttribute("id", "hr_contract_salary");
        const selectWrapperEls = this.el.querySelectorAll(
            "#hr_contract_salary select:not(.refuse-reason-select)"
        );

        // Create a wrapper div to ensure the working schedule selection appears directly below the label TODO: remove master
        const workingScheduleSelect = this.el.querySelector("#hr_contract_salary select[name='simulation_working_schedule']");
        if (workingScheduleSelect) {
            const wrapperDiv = workingScheduleSelect.parentNode.insertBefore(this.el.ownerDocument.createElement("div"), workingScheduleSelect);
            wrapperDiv.append(workingScheduleSelect);
        }

        selectWrapperEls.forEach((el) => {
            this.selectMenus[el.name] = {
                disabled: false,
                choices: [],
                value: el.value,
                groups: [],
                required: el.required,
                autoSort: false,
            };
        });
        
        this.updateGross = debounce(this.updateGross, 1000);
        this.initializeUnsetSliders();
        this.initializePercentFields();
        const whitelist = document.querySelector("input[name='whitelist']")?.value;
        if (whitelist) {
            var whitelisted_fields = whitelist.split(",");
            this.el.querySelectorAll("input").forEach((input) => {
                if (!whitelisted_fields.includes(input.name)) {
                    input.setAttribute("disabled", true);
                }
            });
            for (const [, selectMenuInst] of Object.entries(this.selectMenus)) {
                if (!whitelisted_fields.includes(selectMenuInst)) {
                    selectMenuInst.disabled = true;
                }
            }
        }
        this.stateElements = this.el.querySelector("select[name='private_state_id']")?.querySelectorAll("option");
        this.onchangeCountry();

        // When user use back button, unfold previously unfolded items.
        for (const checkedInputEl of document.querySelectorAll("#hr_cs_configurator .hr_cs_control input.folded:checked")) {
            checkedInputEl.closest("div")
                ?.querySelectorAll(".folded_content")
                .forEach((el) => el.classList.remove("d-none"));
        }

        this.notificationService = this.services.notification;
    }

    async willStart() {
        await this.updateGross();
        await this.setUpBenefits();
    }

    setUpBenefits() {
        // When we load the benefits, if any of the advantage is not set and it has
        // dependent benefits (or requested documents),
        // unset those dependent benefits (or hide those requested documents)
        document.querySelectorAll("input").forEach(async input => {
            let dependentBenefits = input.dataset['benefit_ids-dependent'];
            const requestedDocuments = input.dataset.requested_documents;
            let mandatoryBenefitSelected;
            if (dependentBenefits || requestedDocuments) {
                let newValue = input.dataset.value;
                if (input.type === "radio") {
                    const targetEl = document.querySelector(`input[name='${input.name}']:checked`);
                    newValue = targetEl.dataset.value;
                    if (newValue === "No") {
                        newValue = 0;
                    }
                } else if (input.type === "checkbox") {
                    newValue = input.checked;
                } else {
                    newValue = input.value;
                }
                mandatoryBenefitSelected = Boolean(+newValue);
            }

            if (dependentBenefits && !mandatoryBenefitSelected) {
                this.updateDependentBenefits(dependentBenefits, mandatoryBenefitSelected);
            }
            if (requestedDocuments) {
                requestedDocuments.split(",").forEach(requested_document => {
                    document.querySelector(`div[name='${requested_document}']`)?.classList.toggle("d-none", !mandatoryBenefitSelected);
                });
            }
        });
    }

    initializePercentFields() {
        this.el.querySelectorAll("input.percent-field").forEach(input => {
            const decimalValue = parseFloat(input.value) || 0;
            input.value = decimalValue * 100;
            input.classList.add("percent-field-changed");
        });
    }

    initializeUnsetSliders() {
        document.querySelectorAll("input[type='range']").forEach(input => {
            const inputName = input.name.replace("_slider", "");
            const valueInputEl = document.querySelector(`input[name='${inputName}']`);
            if (valueInputEl && !valueInputEl.value) {
                input.value = 0;
                valueInputEl.value = 0;
            }
        });
    }

    getFileData(documentName) {
        const fileInputEl = document.querySelector(`input[name='${documentName}']`);
        return new Promise(async resolve => {
            if (fileInputEl.files[0]) {
                const testString = await getDataURLFromFile(fileInputEl.files[0]);
                const regex = new RegExp(",(.{0,})", "g");
                const img_src = regex.exec(testString)[1];
                resolve(img_src);
            } else {
                resolve(false);
            }
        });
    }

    async getPersonalDocuments() {
        const documentNames = Array.from(document.querySelectorAll("input[type='file']"))
            .map(input => ({
                name: input.name,
                appliesOn: input.getAttribute("applies-on"),
            }));
        let documentSrcs = {
            'version_personal': {},
            'employee': {},
            'address': {},
            'bank_account': {}
        };
        const promises = documentNames.map(async ({name, appliesOn}) => {
            const docSrc = await this.getFileData(name)
            documentSrcs[appliesOn][name] = docSrc;
        });
        await Promise.all(promises);
        return documentSrcs;
    }

    getBenefits() {
        const benefits = {
            'version_personal': {},
            'version': {},
            'employee': {},
            'address': {},
            'bank_account': {},
        };
        benefits.employee.job_title = document.querySelector("input[name='job_title']")?.value;
        benefits.employee.employee_job_id = document.querySelector("input[name='employee_job_id']")?.value;
        benefits.employee.department_id = document.querySelector("input[name='department_id']")?.value;

        document.querySelectorAll("input[applies-on]:not([type='file'])")
            .forEach(input => {
                const appliesOn = input.getAttribute("applies-on");
                if (input.type === "checkbox") {
                    benefits[appliesOn][input.name] = input.checked;
                } else if (input.type === "radio" && input.checked) {
                    benefits[appliesOn][input.name] = input.dataset.value;
                } else if (input.type !== "hidden" && input.type !== "radio") {
                    benefits[appliesOn][input.name] = input.value;
                }
                if (input.classList.contains('percent-field-changed')){
                    benefits[appliesOn][input.name] = String(benefits[appliesOn][input.name] / 100)
                }
            });
        document.querySelectorAll("textarea[applies-on]")
            .forEach(area => {
                const appliesOn = area.getAttribute("applies-on");
                benefits[appliesOn][area.name] = area.value;
            });
        Array.from(document.querySelectorAll("select.benefit_input,select.personal_info"))
            .filter(select => select.name !== "simulation_working_schedule")
            .forEach(select => {
                const appliesOn = select.getAttribute("applies-on");
                benefits[appliesOn][select.name] = select.value;
            });
        return benefits;
    }

    updateGrossToNetModal(data) {
        const resumeEl = this.el.querySelector("div[name='salary_package_resume']");
        if (resumeEl) {
            resumeEl.classList.remove("d-none");
            resumeEl.replaceChildren();

            this.renderAt(
                "hr_contract_salary.salary_package_resume",
                {
                    lines: data.resume_lines_mapped,
                    categories: data.resume_categories,
                    configurator_warning: data.configurator_warning,
                },
                resumeEl
            );
        }

        const divNet = this.el.querySelector("main.modal-body");
        if (divNet) {
            divNet.classList.remove("d-none");
            divNet.replaceChildren();
            this.renderAt(
                "hr_contract_salary.salary_package_brut_to_net_modal",
                {
                    "data_lines": data.payslip_lines,
                },
                divNet
            );
        }

        const wageInputEl = document.querySelector("input[name='wage']");
        if (wageInputEl) {
            wageInputEl.value = data.wage;
        }
        
        const netDivEl = document.querySelector("div[name='net']");
        if (netDivEl) {
            netDivEl.classList.remove("d-none");
            slideDown(netDivEl, 600);
        }
        document.querySelector("input[name='NET']")?.classList.remove("o_outdated");
    }

    onchangeFoldedResetInteger(benefitField) {
        return true;
    }

    onchangeFolded(event) {
        const foldedContentEl = event.target.parentElement.parentElement.querySelector(".folded_content");
        if (foldedContentEl) {
            const checked = event.target.checked;
            if (!checked) {
                foldedContentEl.querySelectorAll("input")
                    .forEach(input => {
                        if (input.type === "number" && this.onchangeFoldedResetInteger(input.name)) {
                        input.value = 0;
                        input.dispatchEvent(new Event("change", { bubbles: true }));
                        }
                    });
                
            } else {
                foldedContentEl.querySelectorAll("select")
                    .forEach(select => {
                        select.dispatchEvent(new Event("change", { bubbles: true }));
                    });
            }
            foldedContentEl.classList.toggle("d-none", !checked);
        }
        
    }

    onchangeSlider(event) {
        let benefitField = event.target.name.replace("_slider", "");
        document.querySelector(`input[name='${benefitField}']`).value = event.target.value;
    }

    async onchangeCountry(event) {
        const stateElement = document.querySelector("select[name='private_state_id']");
        if (!stateElement) {
            return;
        }
        const selectedStateID = document.querySelector("select[name='private_state_id']").value;
        const countryID = document.querySelector("select[name='private_country_id'][applies-on='version_personal']")?.value;
        let enableState = true;
        const stateSelectMenu = this.selectMenus["private_state_id"];
        stateElement.querySelectorAll("option").forEach((option) => option.remove());
        this.stateElements.forEach((option) => stateElement.appendChild(option));
        stateElement.querySelectorAll("option").forEach((option) => {
            const stateCountryID = option.getAttribute("data-additional-info");
            if (countryID === stateCountryID) {
                enableState = false;

            } else {
                option.remove();
            }
        });
        let selectedIndex = -1;
        for (let i = 0; i < stateElement.length; ++i){
            if (stateElement.options[i].value == selectedStateID){
                selectedIndex = i;
            }
        }
        const choicesEls = [...stateElement.querySelectorAll("option")];
        if (selectedIndex == -1) {
            stateSelectMenu.value = "";
        }
        stateSelectMenu.choices = choicesEls;
        stateSelectMenu.disabled = enableState;
        stateElement.selectedIndex = selectedIndex;
    }

    onkeydownInput(event) {
        const disallowedKeys = [
            "KeyE",
            "NumpadSubtract",
            "NumpadDecimal",
            "Minus",
            "Period"
        ];
        // Only allow numbers to be written in the input fields with type="number"
        return !(event.code in disallowedKeys);
    }

    _isInvalidInput() {
        let isInvalidInput;
        for (const input of document.querySelectorAll("input[data-field-type=integer]")) {
            if (input.value && !Number.isInteger(parseFloat(input.value))) {
                isInvalidInput = true;
                if (!input.classList.contains("border-danger")) {
                    this.notificationService.add(_t("Not a valid input in integer field"), {
                        type: "danger",
                    });
                    input.classList.toggle("border-danger", isInvalidInput);
                }
            } else if(input.classList.contains("border-danger")) {
                input.classList.remove("border-danger");
            }
        }
        return isInvalidInput;
    }

    async onchangeBenefit(event) {
        // Check that https://github.com/odoo/enterprise/commit/e4fdb4df1d0d6aa5e8880ce1b4cc289a075479fd#diff-aa5bcb2caed35c99a7bd3e018a104342 is still valid
        // Will check when the user has entered a floating value in the integer field
        if (this._isInvalidInput()) {
            return false;
        }
        // Prevent negative value for number inputs
        if (event.target.type === "number" && parseFloat(event.target.value) < 0) {
            event.target.value = 0;
        }
        let benefitField = event.target.name;
        if (benefitField.includes("_slider")) {
            benefitField = benefitField.replace("_slider", "");
        } else if (benefitField.includes("_manual")) {
            benefitField = benefitField.replace("_manual", "");
        } else if (benefitField.includes("_radio")) {
            benefitField = benefitField.replace("_radio", "");
        } else if (benefitField.includes("select_")) {
            benefitField = benefitField.replace("select_", "");
        }
        const requestedDocuments = event.target.dataset.requested_documents;
        if (requestedDocuments) {
            let hide;
            if (event.target.type === "number") {
                hide = event.target.value === "0" || event.target.value === "";
            } else if (event.target.type === "checkbox") {
                hide = !event.target.checked;
            } else if (event.target.type === "radio") {
                hide = !!event.target.parentElement.querySelector(".hr_cs_control_no");
            }
            requestedDocuments.split(",").forEach(requested_document => {
                document.querySelector(`div[name='${requested_document}']`)?.classList.toggle("d-none", hide);
            });
        }

        let newValue;
        if (event.target.type === "radio") {
            const targetEl = document.querySelector(`input[name='${event.target.name}']:checked`);
            document.querySelector(`span[name='description_${benefitField}']`)
                ?.classList.toggle("d-none", targetEl.classList.contains("hide_description"));
            newValue = targetEl.dataset.value;
            if (newValue === "No") {
                newValue = 0;
            }
        } else if (event.target.type === "checkbox") {
            newValue = event.target.checked;
        } else {
            newValue = event.target.value;
        }

        const dependentBenefits = event.target.getAttribute("data-benefit_ids-dependent");

        const mandatoryBenefitSelected = Boolean(+newValue);
        this.updateDependentBenefits(dependentBenefits, mandatoryBenefitSelected);
        await this.updateAfterChangingBenefit(event.target.type, benefitField, newValue);
    }

    updateDependentBenefits (dependentBenefits, mandatoryBenefitSelected) {
        if (!dependentBenefits) {
            return;
        }
        dependentBenefits.trim().split(" ").forEach(async dependentBenefit => {
            /*
            Let's say the benefit X depends on A, B, C
            If one of the mandatory benefits, A, is selected
                check that the B and C are selected too - if yes
                    Enable X
            Else
                disable X
            */
            const targetEl = document.querySelector(`input[name='${dependentBenefit}']`);
            if (!mandatoryBenefitSelected) { // Here we unset the dependent benefit
                let dependentBenefitSelected =  this.checkInputSelected(dependentBenefit);
                let dependentBenefitField = dependentBenefit;
                let type = targetEl.type;
                if (dependentBenefit.includes("select_")) {
                    dependentBenefitField = dependentBenefit.replace("select_", "");
                    type = "select";
                } else if (dependentBenefit.includes("manual")) {
                    type = "manual";
                    dependentBenefitField = dependentBenefit.replace("_manual", "");
                } else if (dependentBenefit.includes("_slider")) {
                    type = "slider";
                    dependentBenefitField = dependentBenefit.replace("_slider", "");
                } else if (dependentBenefit.includes("_radio")) {
                    type = "radio";
                    dependentBenefitField = dependentBenefit.replace("_radio", "");
                }
                
                if (dependentBenefitSelected) { // no need to update it if it was not selected to start with
                    let targetType = targetEl.type;
                    if (targetType === "checkbox") {
                        targetEl.click();
                    } else if (targetType === "radio") {
                        const toCheck = targetEl.dataset.value == "0.0" ? targetEl : undefined;
                        toCheck?.click();
                    }
                    targetEl.value = 0;
                    targetEl.dispatchEvent(new Event("change", { bubbles: true }));
                    targetEl.disabled = true;
                    targetEl.parentElement.classList.add("o_disabled");
                    await this.updateAfterChangingBenefit(type, dependentBenefitField, 0);
                }
                targetEl.disabled = true;
                targetEl.parentElement.classList.add("o_disabled");

                const mandatoryBenefitsNames = (targetEl.getAttribute("data-benefit_ids-mandatory-names") || "").trim().split(";").filter(elem => elem !== "");
                const dep = mandatoryBenefitsNames.shift();
                let title = _t("In order to choose %s, first you need to choose:\n %s", dep, mandatoryBenefitsNames.join("\n "));

                targetEl.closest("div").parentElement.title = title;
                targetEl.closest("div").style.cursor = "pointer";
            } else {
                const mandatoryBenefits = (targetEl.getAttribute("data-benefit_ids-mandatory") || "").trim().split(" ");
                const allMandatorySelected = mandatoryBenefits.every(adv => this.checkInputSelected(adv));
                if (allMandatorySelected) {
                    const targets = document.querySelectorAll(`input[name='${dependentBenefit}']:disabled`);
                    if (targets) {
                        targets.forEach(el => el.removeAttribute("disabled"));
                        targetEl.parentElement.classList.remove("o_disabled");
                        targetEl.closest("div").style.cursor = "";
                        targetEl.closest("div").removeAttribute("title");
                    }
                }
            }
            
        });
    }

    checkInputSelected(benefit) {
        const targetEl = Array.from(document.querySelectorAll(`input[name='${benefit}']`))
        if (!targetEl.length) {
            return false;
        }
        let type = targetEl[0].type;
        let newValue;
        if (type === "radio") {
            const checked = targetEl.find(elem => elem.checked);
            newValue = checked?.dataset.value;
        } else if (type === "checkbox") {
            newValue = targetEl[0].checked;
        } else {
            newValue = targetEl[0].value;
        }
        return Boolean(+newValue);
    }

    async updateAfterChangingBenefit(type, benefitField, newValue) {
        if (type !== 'file') {
            const result = await rpc('/salary_package/onchange_benefit', {
                'benefit_field': benefitField,
                'new_value': newValue,
                'offer_id': parseInt(document.querySelector("input[name='offer_id']").value),
                'benefits': this.getBenefits({includeFiles: false}),
                'token': document.querySelector("input[name='token']").value,
            });
            if (type !== "select") {
                const benefitInputEl = document.querySelector(`input[name='${benefitField}']`);
                if (benefitInputEl) {
                    benefitInputEl.value = result.new_value;
                }
            }
            const benefitSpanEl = document.querySelector(`span[name='description_${benefitField}']`);
            if (benefitSpanEl) {
                benefitSpanEl.innerHTML = result.description ? result.description : "";
            }
            const input = this.el.querySelector(`input[name='${benefitField}']`);
            if (input && input.classList.contains('percent-field')) {
                const decimalValue = parseFloat(result.new_value) || 0;
                input.value = decimalValue * 100;
                input.classList.add('percent-field-changed');
            }
            if (result.extra_values) {
                result.extra_values.forEach((extra_value) => {
                    const extraInputEl = document.querySelector(`input[name='${extra_value[0]}']`);
                    if (extraInputEl) {
                        extraInputEl.value = extra_value[1];
                    }
                });
            }
            await this.updateGross();
        }
    }

    async onchangeDocument(input) {
        if (input.target.files && input.target.files.length > 0) {
            const testString = await getDataURLFromFile(input.target.files[0]);
            const regex = new RegExp(",(.{0,})", "g");
            const img_src = regex.exec(testString)[1];
            const isPdfImgSrc = img_src.startsWith("JVBERi0");
            const pdfIframeEl = document.querySelector("iframe#" + input.target.name + "_pdf");
            const imgEl = document.querySelector("img#" + input.target.name + "_img");
            const srcElement = isPdfImgSrc ? pdfIframeEl : imgEl;
            srcElement?.setAttribute("src", testString);
            imgEl?.classList.toggle("d-none", isPdfImgSrc);
            pdfIframeEl?.classList.toggle("d-none", !isPdfImgSrc);
        }
    }

    updateGross() {
        const self = this;
        document.querySelector("input[name='NET']")?.classList.add("o_outdated");
        const selectorsToShow = ["div[name='compute_net']", "a[name='recompute']"];
        const selectorsToHide = ["div[name='net']", "a[name='details']"];
        for (const sel of [...selectorsToShow, ...selectorsToHide]) {
            document.querySelector(sel)?.classList.toggle("d-none", selectorsToHide.includes(sel));
        }
        return this.keepLast.add(
            rpc('/salary_package/update_salary', {
                'offer_id': parseInt(document.querySelector("input[name='offer_id']").value),
                'benefits': self.getBenefits({includeFiles: false}),
                'simulation_working_schedule': document.querySelector("select[name='simulation_working_schedule']")?.value,
                'token': document.querySelector("input[name='token']").value,
            }).then(data => {
                document.querySelector("input[name='wage']").value = data["new_gross"];
                document.querySelector("a[name='recompute']")?.classList.add("d-none");
                document.querySelector("a[name='details']")?.classList.remove("d-none");
                self.updateGrossToNetModal(data);
            })
        );
    }

    async onchangePersonalInfo(event) {
        let newValue;
        if (event.target.type === "radio") {
            document.querySelectorAll(`input[name='${event.target.name}']`).forEach(elem => {
                if (elem.checked) {
                    newValue = elem.dataset.value;
                }
            });
        } else if (event.target.type === "checkbox") {
            newValue = event.target.checked;
        } else {
            newValue = event.target.value;
        }
        const data = await rpc("/salary_package/onchange_personal_info", {
            "field": event.target.name,
            "value": newValue,
        });
        if (Object.keys(data || {}).length > 0) {
            const childDiv = document.querySelector(`div[name='personal_info_child_group_${data.field}']`);
            const childInputs = childDiv?.querySelectorAll("input");
            childDiv?.classList.toggle("d-none", data.hide_children);
            childInputs?.forEach(input => input.required = !data.hide_children);
        }
    }

    recompute() {
        document.querySelector("a[name='details']")?.classList.remove("d-none");
        document.querySelector("a[name='recompute']")?.classList.add("d-none");
        document.querySelector("input[name='NET']")?.classList.remove("o_outdated");
    }

    _isValidEmail(value) {
        const atpos = value.indexOf("@");
        const dotpos = value.lastIndexOf(".");
        return !(atpos < 1 || dotpos < atpos + 2 || dotpos + 2 >= value.length);
    }

    clearFieldError(event) {
        const input = event.target;
        let isValid;
        if (input.name === "private_email") {
            isValid = this._isValidEmail(input.value);
        } else if (input.dataset.fieldType === "integer") {
            isValid = input.value !== "" && Number.isInteger(parseFloat(input.value));
        } else {
            isValid = input.value !== "";
        }
        input.classList.toggle("border-danger", !isValid);
    }

    clearRadioError(event) {
        const wrapperEl = event.currentTarget;
        const hasChecked = Array.from(wrapperEl.querySelectorAll("input[type=radio]")).some(el => el.checked);
        wrapperEl.classList.toggle("invalid_radio", !hasChecked);
    }

    clearSelectError(event) {
        const select = event.target;
        const selectParentEl = select.parentElement.querySelector(".o_select_menu");
        if (selectParentEl) {
            const isFilled = select.value !== "";
            selectParentEl.classList.toggle("border-danger", !isFilled);
            if (isFilled) {
                selectParentEl.querySelectorAll("input.border-danger").forEach(input => {
                    input.classList.remove("border-danger");
                });
            }
        }
    }

    checkFormValidity() {
        // Don't make the input required, if the element is not displayed.
        // For example, we don't want to require driving license
        // when it is not displayed. As it will be conditionally hidden if car advantage is not set.
        const requiredEmptyInput = Array.from(document.querySelectorAll("input:required"))
            .find(input => input.value === "" && input.name !== "" && input.type !== "checkbox" && input.offsetParent !== null);
        const requiredEmptySelect = Array.from(document.querySelectorAll("select:required"))
            .find(select => select.value === "" && select.offsetParent !== null);
        const requiredEmptyTextArea = Array.from(document.querySelectorAll("textarea:required"))
            .find(textarea => textarea.value === "" && textarea.offsetParent !== null);
        const emailEl = document.querySelector("input[name='private_email']");
        const emailValue = emailEl ? emailEl.value : "";
        const isInvalidEmail = !this._isValidEmail(emailValue);
        const isInvalidInput = this._isInvalidInput();
        let elementToScroll;
        let elementToScrollPosition;
        const isEmailEmpty = emailValue === "";

        let requiredEmptyRadio;
        const radios = Array.prototype.slice.call(document.querySelectorAll("input[type=radio]:required"));
        const groups = Object.values(radios.reduce((result, el) => Object.assign(result, {[el.name]: (result[el.name] || []).concat(el)}), {}));
        groups.some((group, index) => {
            const radioEl = group[0].parentElement.parentElement;
            if (!group.some(el => el.checked)) {
                requiredEmptyRadio = true;
                this.notificationService.add(_t("Some required fields are not filled"), {
                    type: "danger",
                });
                radioEl.classList.toggle("invalid_radio", requiredEmptyRadio);
                elementToScroll = radioEl;
                const rect = radioEl.getBoundingClientRect();
                elementToScrollPosition = rect.top + window.scrollY;
            } else if (radioEl.classList.contains("invalid_radio")) {
                radioEl.classList.toggle("invalid_radio");
            }
        });

        if(requiredEmptyInput ||  requiredEmptySelect || requiredEmptyTextArea) {
            this.notificationService.add(_t("Some required fields are not filled"), {
                type: "danger",
            });
            document.querySelectorAll("input:required").forEach(input => {
                input.classList.toggle("border-danger", input.value === "");
                const rect = input.getBoundingClientRect();
                let inputPosition = rect.top + window.scrollY;
                if ((!elementToScroll || inputPosition < elementToScrollPosition) && input.value === "" && input.type !== "checkbox") {
                    elementToScroll = input;
                    elementToScrollPosition = inputPosition;
                }
            });
            document.querySelectorAll("textarea:required").forEach(textarea => {
                textarea.classList.toggle("border-danger", textarea.value === "");
                const rect = textarea.getBoundingClientRect();
                let textareaPosition = rect.top + window.scrollY;
                if ((!elementToScroll || textareaPosition < elementToScrollPosition) && textarea.value === "") {
                    elementToScroll = textarea;
                    elementToScrollPosition = textareaPosition;
                }
            });
            document.querySelectorAll("select:required").forEach(select => {
                const selectParentEl = select.parentElement.querySelector(".o_select_menu");
                if (selectParentEl) {
                    selectParentEl.classList.toggle("border-danger", select.value === "");
                    const rect = selectParentEl.getBoundingClientRect();
                    let selectPosition = rect.top + window.scrollY;
                    if ((!elementToScroll || selectPosition <= elementToScrollPosition) && select.value === "") {
                        elementToScroll = selectParentEl;
                        elementToScrollPosition = selectPosition;
                    }
                }
            });
        }
        else {
            document.querySelectorAll("input:required").forEach(input => {
                input.classList.remove("border-danger");
            })
            document.querySelectorAll("textarea:required").forEach(textarea => {
                textarea.classList.remove("border-danger");
            })
            document.querySelectorAll("select:required").forEach(select => {
                const selectParentEl = select.parentElement.querySelector(".o_select_menu");
                if (selectParentEl && select.value !== "") {
                    selectParentEl.classList.remove("border-danger");
                }
            })
        }

        let isCustomFieldsValid = true;
        if (this._fieldValidators){
            Object.keys(this._fieldValidators).forEach(fieldName => {
                isCustomFieldsValid &&= this._validateField(fieldName, true);
            });
        }

        if (isInvalidEmail) {
            document.querySelector("input[name='private_email']")?.classList.add("border-danger");
            if (!isEmailEmpty) {
                this.notificationService.add(_t("Not a valid e-mail address"), {
                    type: "danger",
                });
            }
            const rect = document.querySelector("input[name='private_email']")?.getBoundingClientRect();
            let emailPosition = rect?.top + window.scrollY;
            if (!elementToScroll || emailPosition <= elementToScrollPosition) {
                elementToScroll = document.querySelector("input[name='private_email']");
            }
        }
        if (elementToScroll) {
            elementToScroll.scrollIntoView({block: "center", behavior: "smooth"});
        }
        return !isInvalidEmail && !requiredEmptyInput && !requiredEmptySelect && !requiredEmptyTextArea && !requiredEmptyRadio && !isInvalidInput && isCustomFieldsValid;
    }

    _validateField(fieldName, showNotification = false) {
        const config = this._fieldValidators[fieldName];
        if (!config) return true;

        const inputEl = this.el.querySelector(`input[name='${fieldName}'][applies-on='version_personal']`);
        if (!inputEl || inputEl.offsetParent === null) return true;

        const isValid = config.validator.call(this, inputEl.value);
        inputEl.classList.toggle(config.errorClass, !isValid);

        if (!isValid && showNotification) {
            this.notificationService.add(_t(config.errorMessage), { type: "danger" });
            inputEl.scrollIntoView({ block: "center", behavior: "smooth" });
        }
        return isValid;
    }

    async getFormInfo() {
        const personalDocuments = await this.getPersonalDocuments();
        let benefits = this.getBenefits();
        benefits = {
            'employee': Object.assign(benefits.employee, personalDocuments.employee),
            'version': Object.assign(benefits.version, personalDocuments.version),
            'version_personal': Object.assign(benefits.version_personal, personalDocuments.version_personal),
            'address': Object.assign(benefits.address, personalDocuments.address),
            'bank_account': Object.assign(benefits.bank_account, personalDocuments.bank_account),
        }
        //. and - characters are separated while transferring to the niss field in hr.employee
        const countryCode = document.querySelector("input[name='country_code']")?.value;
        if (countryCode == 'BE'){
            benefits.version_personal.niss = benefits.version_personal.niss.replace(/[,.\-\s]/g, "");
        }

        return {
            'token': document.querySelector("input[name='token']").value,
            'benefits': benefits,
            'offer_id': parseInt(document.querySelector("input[name='offer_id']").value) || false,
            'original_link': document.querySelector("input[name='original_link']").value
        };
    }

    async submitSalaryPackage(event) {
        if (this.checkFormValidity()) {
            const formInfo = await this.getFormInfo();
            const data = await rpc("/salary_package/submit", formInfo);
            if (data["error"]) {
                this.notificationService.add(data["error_msg"], {
                    type: "danger",
                });
            } else {
                document.location.pathname = "/sign/document/" + data["request_id"] + "/" + data["token"];
            }
        }
    }

    async submitFeedback() {
        const feedbackEl = document.querySelector("#feedback-textarea");
        const offer_id = parseInt(document.querySelector("input[name='offer_id']").value) || false;
        const feedbackValue = feedbackEl && feedbackEl.value;
        const token = document.querySelector("input[name='token']").value;
        if (!feedbackValue) {
            return;
        }
        const res = await rpc("/salary_package/post_feedback/", {
            feedback: feedbackValue,
            offer_id: offer_id,
            token,
        })
        if (res) {
            const feedbackFormSuccessEl = document.querySelector("#feedback-form-success");
            feedbackFormSuccessEl.style.display = "";

            setTimeout(() => {
                feedbackFormSuccessEl.style.display = "none";
                feedbackEl.value = "";
                document.querySelector("#feedback-form").classList.remove("show");
            }, 3000);
        }
    }

    togglePersonalInformation() {
        document.querySelectorAll("button[name='toggle_personal_information']").forEach(btn => {
            btn.classList.toggle("d-none");
        });
        const personalInfoDiv = document.querySelector("div[name='personal_info']");
        if (personalInfoDiv) {
            slideToggle(personalInfoDiv, 500);
        }
        const personalInfoTaxDiv = document.querySelector("div[name='personal_info_withholding_taxes']");
        if (personalInfoTaxDiv) {
            slideToggle(personalInfoTaxDiv, 500);
        }
    }
}

registry
    .category("public.interactions")
    .add("hr_contract_salary.salary_package", SalaryPackage);

function setSlideable(el) {
    if (!el.classList.contains("o_slideable")) {
        const style = window.getComputedStyle(el);
        const isVisible = style.display !== "none" && el.offsetHeight > 0;

        el.classList.add("o_slideable");

        if (!isVisible) {
            el.classList.add("closed");
        }
    }
}

function setupSlide(el, duration) {
    setSlideable(el);
    el.style.setProperty("--slide-duration", duration + "ms");
    el.style.setProperty("--slide-height", el.scrollHeight + "px");
}

function slideDown(el, duration) {
    setupSlide(el, duration);
    el.classList.remove("closed");
}

function slideUp(el, duration) {
    setupSlide(el, duration);
    el.classList.add("closed");
}

function slideToggle(el, duration) {
    setSlideable(el);
    const isClosed = el.classList.contains("closed");
    if (isClosed) {
        slideDown(el, duration);
    } else {
        slideUp(el, duration);
    }
}
