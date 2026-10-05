import { _t } from "@web/core/l10n/translation";
import { SalaryPackage } from "@hr_contract_salary/interactions/hr_contract_salary";
import { renderToElement } from "@web/core/utils/render";
import { patch } from "@web/core/utils/patch";
import { patchDynamicContent } from "@web/public/utils";

patch(SalaryPackage.prototype, {

    setup() {
        super.setup();
        this._fieldValidators = {
            niss: {
                validator: (value) => {
                    const countryCode = document.querySelector("input[name='country_code']")?.value;
                    if (countryCode !== 'BE') 
                        return true;
                    const niss = (value || "").replace(/[,.\-\s]/g, "");
                    if (niss === "") return true;
                    if (!/^\d{11}$/.test(niss)) return false;
                    let test = niss.slice(0, -2);
                    const currentYear = new Date().getFullYear() % 100;
                    if (parseInt(test.slice(0, 2), 10) < currentYear) test = `2${test}`;
                    const checksum = parseInt(niss.slice(-2), 10);
                    return checksum === (97 - (parseInt(test, 10) % 97));
                },
                errorClass: 'border-danger',
                errorMessage: _t('Invalid NISS.'),
            },
        };
        patchDynamicContent(this.dynamicContent, {
            "input[name='has_hospital_insurance_radio']": {
                "t-on-change": this.onchangeHospital.bind(this),
            },
            "input[name='insured_relative_children_manual']": {
                "t-on-change": this.onchangeHospital.bind(this),
            },
            "input[name='insured_relative_adults_manual']": {
                "t-on-change": this.onchangeHospital.bind(this),
            },
            "input[name='fold_insured_relative_spouse']": {
                "t-on-change": this.onchangeHospital.bind(this),
            },
            "input[name='fold_company_car_total_depreciated_cost']": {
                "t-on-change": this.onchangeCompanyCar.bind(this),
            },
            "select[name='select_company_car_total_depreciated_cost']": {
                "t-on-change": this.onchangeCompanyCarOption.bind(this),
            },
            "select[name='select_temporary_car_total_depreciated_cost']": {
                "t-on-change": this.onchangeTemporaryCarOption.bind(this),
            },
            "input[name='private_car_reimbursed_amount_manual']": {
                "t-on-change": this.onchangePrivateCar.bind(this),
            },
            "input[name='fold_l10n_be_bicyle_cost']": {
                "t-on-change": this.onchangePrivateBike.bind(this),
            },
            "input[name='l10n_be_bicyle_cost_manual']": {
                "t-on-change": this.onchangePrivateBike.bind(this),
            },
            "input[name='l10n_be_has_ambulatory_insurance_radio']": {
                "t-on-change": this.onchangeAmbulatory.bind(this),
            },
            "input[name='l10n_be_ambulatory_insured_children_manual']": {
                "t-on-change": this.onchangeAmbulatory.bind(this),
            },
            "input[name='l10n_be_ambulatory_insured_adults_manual']": {
                "t-on-change": this.onchangeAmbulatory.bind(this),
            },
            "input[name='fold_l10n_be_ambulatory_insured_spouse']": {
                "t-on-change": this.onchangeAmbulatory.bind(this),
            },
            "input[name='children']": {
                "t-on-change": this.onchangeChildren.bind(this),
            },
            "input[name='fold_temporary_car_total_depreciated_cost']": {
                "t-on-change": this.onchangeTemporaryCar.bind(this),
            },
            "input[name='fold_l10n_be_mobility_budget_amount_monthly']": {
                "t-on-change": this.onchangeMobility.bind(this),
            },
        });
    },

    setUpBenefits() {
        super.setUpBenefits(...arguments);
        this.el.querySelector
            ("label[for='temporary_car_total_depreciated_cost']")?.parentElement?.classList.add("d-none");
        this.el.querySelector
            ("input[name='fold_temporary_car_total_depreciated_cost']")?.parentElement?.classList.add("d-none");
        const car_options = this.el.querySelector
            ("input[name='new_car_options']")?.value;
        
        if (car_options === 'none') {
            this.el.querySelector("label[for='company_car_total_depreciated_cost']")?.nextElementSibling?.classList.add("o_disabled");
            this.el.querySelector("input[name='company_car_total_depreciated_cost']")?.parentElement?.classList.add("o_disabled");
        }
        const companyCarCost = this.el.querySelector("input[name='company_car_total_depreciated_cost']")?.parentElement
        const temporaryCarCost = this.el.querySelector("input[name='temporary_car_total_depreciated_cost']")?.parentElement
        companyCarCost?.insertAdjacentElement('afterend', temporaryCarCost);
        temporaryCarCost?.classList.add('d-none');
        const fuelCardSlider = this.el.querySelector("input[name='fuel_card_slider']");
        if (fuelCardSlider) {
            const mandatoryBenefits = fuelCardSlider.dataset.benefit_idsMandatory;
            if (mandatoryBenefits) {
                const anyMandatorySelected = mandatoryBenefits.trim().split(' ').some(adv => this.checkInputSelected(adv));

                if (!anyMandatorySelected) {
                    fuelCardSlider.setAttribute("disabled", "disabled");
                    fuelCardSlider.parentElement.classList.add('o_disabled');
                }
            }
        }
    },

    updateGrossToNetModal(data) {
        super.updateGrossToNetModal(data);
        const dblHolidayWageEl = this.el.querySelector("input[name='double_holiday_wage']");
        if (dblHolidayWageEl) {
            dblHolidayWageEl.value = data["double_holiday_wage"];
        }
        if (data["wishlist_simulation"]) {
            const modal_body = renderToElement("hr_contract_salary.salary_package_resume", {
                "lines": data.wishlist_simulation.resume_lines_mapped,
                "categories": data.wishlist_simulation.resume_categories,
                "configurator_warning": data.wishlist_warning,
                "hide_details": true,
            });
            const wishlistModalEl = this.el.querySelector("main[name='wishlist_modal_body']");
            wishlistModalEl.textContent = "";
            wishlistModalEl.appendChild(modal_body);
        }
        // Two buttons on the page have the same ID, so for this specific ID we need to querySelectorAll
        document.querySelectorAll("button#hr_cs_submit").forEach(el => el.disabled = !!data["configurator_warning"]);

        const inputEl = document.querySelector("input[name='l10n_be_mobility_budget_amount_monthly']");
        if (inputEl) {
            inputEl.value = data["l10n_be_mobility_budget_amount_monthly"];
        }
    },

    onchangeCompanyCar(event) {
        const privateCarInputEl = this.el.querySelector(
            "input[name='private_car_reimbursed_amount_manual']"
        );
        const privateCarEl = this.el.querySelector(
            "label[for='private_car_reimbursed_amount']"
        )
        const temporaryCarInputEl = this.el.querySelector
            ("input[name='fold_temporary_car_total_depreciated_cost']")
        const temporaryCarOptionEl = this.el.querySelector
            ("label[for='temporary_car_total_depreciated_cost']")
        const carList = this.el.querySelector("select[name='select_company_car_total_depreciated_cost']")
        const tempList = this.el.querySelector("select[name='select_temporary_car_total_depreciated_cost']")
            

        if (event.target.checked) {
            if(privateCarInputEl && privateCarInputEl.value){
                privateCarInputEl.value = 0;
            }
            privateCarEl?.parentElement.classList.add("o_disabled");
            if (carList?.value.split('-')[0] === "new" && tempList?.value) {
                this.hideElements(false);
            }
            else {
                this.hideElements(true);
            }

        }
        if (!event.target.checked){
            temporaryCarOptionEl?.parentElement?.classList.add("d-none");
            privateCarEl?.parentElement.classList.remove("o_disabled");
            if (temporaryCarInputEl?.checked) {
                temporaryCarInputEl.click()
            }
        }
    },
    onchangeCompanyCarOption(event) {
        const tempCarSetting = this.el.querySelector("input[name='l10n_be_temporary_car_option']")?.value;
        const temporaryCarInputEl = this.el.querySelector
            ("input[name='fold_temporary_car_total_depreciated_cost']")
        const temporaryCarOptionEl = this.el.querySelector
            ("label[for='temporary_car_total_depreciated_cost']")
        const tempList = this.el.querySelector("select[name='select_temporary_car_total_depreciated_cost']")
        const listOfOptions = tempList?.options
        const carVersion = event.target.value.split('-')[0]
        
        if (carVersion === "new" && tempCarSetting === 'True' && (listOfOptions?.length ?? 0) > 1) {
            temporaryCarOptionEl.parentElement?.classList.remove("d-none");
            if (temporaryCarInputEl && !temporaryCarInputEl.checked) {
                temporaryCarInputEl.click()
                if (!tempList?.value) {
                    this.hideElements(true);
                }
                else {
                    this.hideElements(false);
                }
            }
        }
        else {
            this.el.querySelector("input[name='company_car_total_depreciated_cost']")?.parentElement.classList.remove("d-none");
            this.el.querySelector("input[name='temporary_car_total_depreciated_cost']")?.parentElement.classList.add("d-none");
            temporaryCarOptionEl?.parentElement?.classList.add("d-none");
            if (temporaryCarInputEl?.checked) {
                temporaryCarInputEl.click()
            }
        }
    },
    onchangeTemporaryCarOption(event) {
        if (!event.target.value) {
            this.hideElements(true);
            this.el.querySelector("input[name='company_car_total_depreciated_cost']")?.parentElement.classList.remove("d-none");
            this.el.querySelector("input[name='temporary_car_total_depreciated_cost']")?.parentElement.classList.add("d-none");
        }
        else {
            this.hideElements(false);
            this.el.querySelector("input[name='company_car_total_depreciated_cost']")?.parentElement.classList.add("d-none");
            this.el.querySelector("input[name='temporary_car_total_depreciated_cost']")?.parentElement.classList.remove("d-none");

        }
        
    },
    onchangePrivateCar(event) {
        const companyCarInputEl = this.el.querySelector(
            "input[name='fold_company_car_total_depreciated_cost']"
        );
        const temporaryCarInputEl = this.el.querySelector(
            "input[name='fold_temporary_car_total_depreciated_cost']"
        );
        if(event.target.value > 0){
            if(companyCarInputEl && companyCarInputEl.checked){
                companyCarInputEl.click();
            }
            if(temporaryCarInputEl && temporaryCarInputEl.checked){
                temporaryCarInputEl.click();
            }
            companyCarInputEl?.parentElement.classList.add("o_disabled");
            temporaryCarInputEl?.parentElement.classList.add("o_disabled");    
        }
        else{
            companyCarInputEl?.parentElement.classList.remove("o_disabled");
            temporaryCarInputEl?.parentElement.classList.remove("o_disabled");    
        }
    },
    onchangeTemporaryCar(event) {
        if (event.target.checked) {
            const tempLabel = document.createElement("div");
            const labelDiv = document.createElement("div");
            labelDiv.classList.add("fw-bold", "mb-2");
            labelDiv.textContent = _t("Choose a temporary car as we wait for the ordered one.");
            tempLabel.appendChild(labelDiv);
            tempLabel.setAttribute("name", 'temp_option_label');
            const tempSelector = this.el.querySelector(
                "select[name='select_temporary_car_total_depreciated_cost']"
            );
            tempSelector.parentElement.insertBefore(
                tempLabel,
                tempSelector,
            );
            const costInput = this.el.querySelector(
                "input[name='temporary_car_total_depreciated_cost']"
            ).parentElement;
            const tempCarEl = document.createElement("strong");
            tempCarEl.setAttribute("name", "temp_car_span")
            tempCarEl.classList.add("text-warning");
            tempCarEl.textContent = _t("Temporary Car");
            costInput.after(
                tempCarEl);
            
            const tempAlertEl = document.createElement("div");
            const simulateDiv = document.createElement("div");
            simulateDiv.textContent = _t("Your salary will be revised when receiving the new car.");
            simulateDiv.classList.add("alert", "alert-warning");
            tempAlertEl.appendChild(simulateDiv);
            tempAlertEl.setAttribute('name', "alert_div")
            const anchorEl = document.createElement("a");
            anchorEl.classList.add( "btn-link", "ms-1");
            anchorEl.setAttribute("role", "button");
            anchorEl.dataset.bsToggle = "modal";
            anchorEl.dataset.bsTarget = "#hr_cs_modal_wishlist";
            anchorEl.dataset.bsBackdrop = "false";
            anchorEl.dataset.bsDismiss = "modal";
            anchorEl.setAttribute("name", "temporary_simulation_button");
            anchorEl.textContent = _t("Simulate");
            tempAlertEl.querySelector(".alert").appendChild(anchorEl);
            const descriptionSpan = this.el.querySelector(
                "span[name='description_temporary_car_total_depreciated_cost']"
            );
            descriptionSpan.after(
                tempAlertEl,
            );

        } else {
            ["strong[name='temp_car_span']", "div[name='alert_div']", "div[name='temp_option_label']"]
        .forEach((sel) => this.el.querySelector(sel)?.remove());
        }
    },
    hideElements(value) {
        if (value) {
            this.el.querySelector("strong[name='temp_car_span']")?.classList.add('d-none')
            this.el.querySelector("div[name='alert_div']")?.classList.add('d-none')
        }
        else {
            this.el.querySelector("strong[name='temp_car_span']")?.classList.remove('d-none')
            this.el.querySelector("div[name='alert_div']")?.classList.remove('d-none')
        }
    },
    onchangePrivateBike: function() {
        const privateBikeCheckboxEl = this.el.querySelector("input[name='fold_l10n_be_bicyle_cost']");
        const privateBikeInputEl = this.el.querySelector("input[name='l10n_be_bicyle_cost_manual']");
        
        const isCheckboxChecked = privateBikeCheckboxEl?.checked || false;
        const privateBikeValue = parseFloat(privateBikeInputEl?.value || "0.0");
        
        if (isCheckboxChecked && privateBikeValue > 0) {
            // Set the fuel card values to 0 and disable it
            const fuelCardSliderEl = this.el.querySelector("input[name='fuel_card_slider']");
            const fuelCardEl = this.el.querySelector("input[name='fuel_card']");
            if (fuelCardSliderEl) {
                fuelCardSliderEl.value = 0;
            }
            if (fuelCardEl) {
                fuelCardEl.value = 0;
            }
            this.el.querySelector("label[for='fuel_card']")?.parentElement.classList.add("o_disabled");
        } else {
            // Enable the fuel card element when checkbox is unchecked or value is 0
            this.el.querySelector("label[for='fuel_card']")?.parentElement.classList.remove("o_disabled");
        }
    },

    onchangeFoldedResetInteger(benefitField) {
        if (benefitField === "private_car_employee_kilometer" || benefitField === "l10n_be_bicyle_cost_manual") {
            return false;
        } else {
            return super.onchangeFoldedResetInteger(benefitField);
        }
    },

    onchangeMobility(event) {
        const hasMobility = this.el.querySelector(`input[name='fold_l10n_be_mobility_budget_amount_monthly']`)?.checked;
        const transportRelatedFieldsFolder = [
            "fold_company_car_total_depreciated_cost",
            "fold_l10n_be_bicyle_cost",
            "fold_temporary_car_total_depreciated_cost",
        ];
        const transportRelatedFields = [
            "bus_transport_reimbursed_amount",
            "metro_transport_reimbursed_amount",
            "tram_transport_reimbursed_amount",
            "train_transport_reimbursed_amount",
            "private_car_reimbursed_amount",
        ]
        if (hasMobility) {
            for (const fieldName of transportRelatedFieldsFolder) {
                const element = this.el.querySelector(`input[name='${fieldName}']`);
                if (element && element.checked) {
                    element.click();
                }
            }
            for (const fieldName of transportRelatedFields) {
                var element = this.el.querySelector(`input[name='${fieldName}']`);
                if (element) {
                    element.value = 0;
                }
                element = this.el.querySelector(`input[name='${fieldName}_manual']`);
                if (element) {
                    element.value = 0;
                }
            }

            const fuelCardSliderEl = this.el.querySelector("input[name='fuel_card_slider']");
            const fuelCardEl = this.el.querySelector("input[name='fuel_card']");
            if (fuelCardSliderEl) {
                fuelCardEl.value = 0;
                fuelCardEl.disabled = true;
            }
            if (fuelCardEl) {
                fuelCardEl.value = 0;
            }

            this.el.querySelector("label[for='company_car_total_depreciated_cost']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='temporary_car_total_depreciated_cost']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='bus_transport_reimbursed_amount']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='bus_transport_periodicity']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='metro_transport_reimbursed_amount']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='metro_transport_periodicity']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='tram_transport_reimbursed_amount']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='tram_transport_periodicity']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='train_transport_reimbursed_amount']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='train_transport_periodicity']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='private_car_reimbursed_amount']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='bike_reimbursed_amount']")?.parentElement.classList.add("o_disabled");
            this.el.querySelector("label[for='fuel_card']")?.parentElement.classList.add("o_disabled");
        } else {
            this.el.querySelector("label[for='company_car_total_depreciated_cost']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='temporary_car_total_depreciated_cost']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='bus_transport_reimbursed_amount']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='bus_transport_periodicity']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='metro_transport_reimbursed_amount']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='metro_transport_periodicity']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='tram_transport_reimbursed_amount']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='tram_transport_periodicity']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='train_transport_reimbursed_amount']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='train_transport_periodicity']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='private_car_reimbursed_amount']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='bike_reimbursed_amount']")?.parentElement.classList.remove("o_disabled");
            this.el.querySelector("label[for='fuel_card']")?.parentElement.classList.remove("o_disabled");
        }
    },


    async willStart() {
        const res = await super.willStart();
        this.onchangeChildren();
        this.onchangeHospital();
        // Hack to make these benefits required. TODO: remove when required benefits are supported.
        this.el
            .querySelector("textarea[name='l10n_be_hospital_insurance_notes_text']")
            ?.setAttribute("required", true);
        this.el
            .querySelector("textarea[name='l10n_be_ambulatory_insurance_notes_text']")
            ?.setAttribute("required", true);
        this.el
            .querySelector("input[name='insured_relative_children']")
            ?.parentElement.classList.add("d-none");
        this.el
            .querySelector("input[name='insured_relative_adults']")
            ?.parentElement.classList.add("d-none");
        this.el
            .querySelector("input[name='insured_relative_spouse']")
            ?.parentElement.classList.add("d-none");
        this.el
            .querySelector("input[name='l10n_be_hospital_insurance_notes']")
            ?.parentElement.classList.add("d-none");
        const childrenEl = this.el.querySelector("input[name='insured_relative_children_manual']");
        const childrenStrongEl = document.createElement("strong");
        childrenStrongEl.classList.add("mt8");
        childrenStrongEl.textContent = _t("# Children < 19");
        childrenEl?.parentNode.insertBefore(childrenStrongEl, childrenEl);

        const adultsEl = this.el.querySelector("input[name='insured_relative_adults_manual']");
        const adultStrongEl = document.createElement("strong");
        adultStrongEl.classList.add("mt8");
        adultStrongEl.textContent = _t("# Children >= 19");
        adultsEl?.parentNode.insertBefore(adultStrongEl, adultsEl);

        const insuranceEl = this.el.querySelector(
            "textarea[name='l10n_be_hospital_insurance_notes_text']"
        );
        const insuranceNoteStrongEl = document.createElement("strong");
        insuranceNoteStrongEl.classList.add("mt8");
        insuranceNoteStrongEl.textContent = _t("Additional Information");
        insuranceEl?.parentNode.insertBefore(insuranceNoteStrongEl, insuranceEl);
        this.onchangeAmbulatory();
        this.el
            .querySelector("input[name='l10n_be_ambulatory_insured_children']")
            ?.parentElement.classList.add("d-none");
        this.el
            .querySelector("input[name='l10n_be_ambulatory_insured_adults']")
            ?.parentElement.classList.add("d-none");
        this.el
            .querySelector("input[name='l10n_be_ambulatory_insured_spouse']")
            ?.parentElement.classList.add("d-none");
        this.el
            .querySelector("input[name='l10n_be_ambulatory_insurance_notes']")
            ?.parentElement.classList.add("d-none");
        const ambulatoryChildrenEl = this.el.querySelector(
            "input[name='l10n_be_ambulatory_insured_children_manual']"
        );
        ambulatoryChildrenEl?.parentNode.insertBefore(
            childrenStrongEl.cloneNode(true), ambulatoryChildrenEl
        );

        const ambulatoryAdultEl = this.el.querySelector(
            "input[name='l10n_be_ambulatory_insured_adults_manual']"
        );
        ambulatoryAdultEl?.parentNode.insertBefore(
            adultStrongEl.cloneNode(true), ambulatoryAdultEl
        );

        const ambulatoryInsuranceEl = this.el.querySelector(
            "textarea[name='l10n_be_ambulatory_insurance_notes_text']"
        );
        ambulatoryInsuranceEl?.parentNode.insertBefore(
            insuranceNoteStrongEl.cloneNode(true), ambulatoryInsuranceEl
        );
        this.onchangeMobility();
        return res;
    },

    onchangeHospital() {
        const insuranceRadioEls = this.el.querySelectorAll(
            "input[name='has_hospital_insurance_radio']"
        );
        const hasInsurance = insuranceRadioEls[insuranceRadioEls.length - 1]?.checked;
        if (hasInsurance) {
            // Show fields
            this.el
                .querySelector("label[for='insured_relative_children']")
                .parentElement.classList.remove("d-none");
            this.el
                .querySelector("label[for='insured_relative_adults']")
                .parentElement.classList.remove("d-none");
            this.el
                .querySelector("label[for='insured_relative_spouse']")
                .parentElement.classList.remove("d-none");
            this.el
                .querySelector("label[for='l10n_be_hospital_insurance_notes']")
                .parentElement.classList.remove("d-none");
            // Only show notes when either an extra spouse or children are insured.
            const insuredSpouse = this.el
                .querySelector("input[name='fold_insured_relative_spouse']")
                ?.checked;
            const insuredRelativeChildren =
                parseInt(
                    this.el.querySelector("input[name='insured_relative_children_manual']").value
                ) > 0;
            const insuredRelativeAdults =
                parseInt(
                    this.el.querySelector("input[name='insured_relative_adults_manual']").value
                ) > 0;
            if (insuredSpouse || insuredRelativeChildren || insuredRelativeAdults ) {
                this.el
                    .querySelector("label[for='l10n_be_hospital_insurance_notes']")
                    .parentElement.classList.remove("d-none");
            }
            else {
                this.el
                    .querySelector("label[for='l10n_be_hospital_insurance_notes']")
                    .parentElement.classList.add("d-none");
            }
        } else {
            // Reset values
            this.el.querySelector("input[name='fold_insured_relative_spouse']")?.removeAttribute("checked");
            const relativeChildrenEl = this.el
                .querySelector("input[name='insured_relative_children_manual']");
            const relativeAdultsEl = this.el
                .querySelector("input[name='insured_relative_adults_manual']");
            if (relativeChildrenEl) {
                relativeChildrenEl.value = 0;
            }
            if (relativeAdultsEl) {
                relativeAdultsEl.value = 0;
            }
            // Hide fields
            this.el
                .querySelector("label[for='insured_relative_children']")
                ?.parentElement.classList.add("d-none");
            this.el
                .querySelector("label[for='insured_relative_adults']")
                ?.parentElement.classList.add("d-none");
            this.el
                .querySelector("label[for='insured_relative_spouse']")
                ?.parentElement.classList.add("d-none");
            this.el
                .querySelector("label[for='l10n_be_hospital_insurance_notes']")
                ?.parentElement.classList.add("d-none");
        }
    },

    onchangeAmbulatory() {
        const insuranceRadiosEls = this.el.querySelectorAll(
            "input[name='l10n_be_has_ambulatory_insurance_radio']"
        );
        const hasInsurance = insuranceRadiosEls[insuranceRadiosEls.length - 1]?.checked;
        if (hasInsurance) {
            // Show fields
            this.el
                .querySelector("label[for='l10n_be_ambulatory_insured_children']")
                .parentElement.classList.remove("d-none");
            this.el
                .querySelector("label[for='l10n_be_ambulatory_insured_adults']")
                .parentElement.classList.remove("d-none");
            this.el
                .querySelector("label[for='l10n_be_ambulatory_insured_spouse']")
                .parentElement.classList.remove("d-none");
            this.el
                .querySelector("label[for='l10n_be_ambulatory_insurance_notes']")
                .parentElement.classList.remove("d-none");
            // Only show notes when either an extra spouse or children are insured.
            const insuredSpouse = this.el
                .querySelector("input[name='fold_l10n_be_ambulatory_insured_spouse']")
                ?.checked;
            const insuredRelativeChildren =
                parseInt(
                    this.el.querySelector(
                        "input[name='l10n_be_ambulatory_insured_children_manual']"
                    ).value
                ) > 0;
            const insuredRelativeAdults =
                parseInt(
                    this.el.querySelector("input[name='l10n_be_ambulatory_insured_adults_manual']")
                        .value
                ) > 0;
            if (insuredSpouse || insuredRelativeChildren || insuredRelativeAdults ) {
                this.el
                    .querySelector("label[for='l10n_be_ambulatory_insurance_notes']")
                    .parentElement.classList.remove("d-none");
            } else {
                this.el
                    .querySelector("label[for='l10n_be_ambulatory_insurance_notes']")
                    .parentElement.classList.add("d-none");
            }
        } else {
            // Reset values
            this.el.querySelector(
                "input[name='fold_l10n_be_ambulatory_insured_spouse']"
            )?.removeAttribute("checked")
            const ambulatoryChildrenEl = this.el
                .querySelector("input[name='l10n_be_ambulatory_insured_children_manual']");
            const ambulatoryAdultsEl = this.el
                .querySelector("input[name='l10n_be_ambulatory_insured_adults_manual']");
            if (ambulatoryChildrenEl) {
                ambulatoryChildrenEl.value = 0;
            }
            if (ambulatoryAdultsEl) {
                ambulatoryAdultsEl.value = 0;
            }
            // Hide fields
            this.el
                .querySelector("label[for='l10n_be_ambulatory_insured_children']")
                ?.parentElement.classList.add("d-none");
            this.el
                .querySelector("label[for='l10n_be_ambulatory_insured_adults']")
                ?.parentElement.classList.add("d-none");
            this.el
                .querySelector("label[for='l10n_be_ambulatory_insured_spouse']")
                ?.parentElement.classList.add("d-none");
            this.el
                .querySelector("label[for='l10n_be_ambulatory_insurance_notes']")
                ?.parentElement.classList.add("d-none");
        }
    },

    onchangeChildren(event) {
        const disabledChildrenNumberEl = this.el.querySelector(
            "input[name='disabled_children_number']"
        );
        const childCount = parseInt(event && event.currentTarget && event.currentTarget.value);

        if (isNaN(childCount) || childCount === 0) {
            if (disabledChildrenNumberEl) {
                disabledChildrenNumberEl.value = 0;
            }
        }
    },
});
