"use_strict";

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import { markup } from "@odoo/owl";

registry.category("web_tour.tours").add('sale_subscription_tour', {
    steps: () => [{
    trigger: '.o_app[data-menu-xmlid="sale_subscription.menu_sale_subscription_root"]',
	content: _t('Want a recurring billing through subscription management? Get started by clicking here'),
    tooltipPosition: 'bottom',
    run: "click",
},
{
    trigger: '.dropdown-toggle[data-menu-xmlid="sale_subscription.product_menu_catalog"]',
    content: _t('Let\'s go to the catalog to create our first subscription product'),
    tooltipPosition: 'bottom',
    run: "click",
},
{
    trigger: '.dropdown-item[data-menu-xmlid="sale_subscription.menu_sale_subscription_product"]',
    content: _t('Create your first subscription product here'),
    tooltipPosition: 'right',
    run: "click",
},
{
    trigger: '.o_kanban_renderer',
},
{
    trigger: '.o-kanban-button-new',
    content: _t('Go ahead and create a new product'),
    tooltipPosition: 'right',
    run: "click",
},
{
    trigger: '.o_form_editable',
},
{
    trigger: '#name_0',
    content: markup(_t('Choose a product name.<br/><i>(e.g. eLearning Access)</i>')),
    tooltipPosition: 'right',
    run: "edit eLearning Access",
},
{
    trigger: '.o_form_editable',
},
{
    trigger: 'button.nav-link[name="sales_price"]',
    content: _t("Let's add a pricing with a recurrence"),
    tooltipPosition: 'right',
    run: "click",
},
{
    trigger: '.o_form_editable',
},
{
    trigger: ".o_field_x2many_list_row_add > button",
    content: _t("Add a new rule"),
    run: "click",
},
{
    trigger: '.o_form_editable',
},
{
    trigger: '.o_list_many2one[name="plan_id"]',
    content: _t("Add a recurring plan for this product, or create a new one with the desired recurrence (e.g., Monthly)"),
    run: "click",
},
...stepUtils.searchOrCreateMany2X(
    '.o_list_many2one[name="plan_id"] input',
    "recurring plan",
    "Monthly",
    {},
    true
),
{
    trigger: '.o_form_editable',
},
{
    trigger: '.o_field_cell[name="fixed_price"]',
    content: _t("Let's add price for selected recurrence"),
    run: "click",
},
{
    trigger: '.dropdown-toggle[data-menu-xmlid="sale_subscription.menu_sale_subscription"]',
    content: _t('Go back to the subscription view'),
    tooltipPosition: 'bottom',
    run: "click",
},
{
    trigger: '.dropdown-item[data-menu-xmlid="sale_subscription.menu_sale_subscription_action"]',
    content: _t('Go back to the subscription view'),
    tooltipPosition: 'right',
    run: "click",
},
{
    trigger: 'button.o_list_button_add',
    content: _t('Go ahead and create a new subscription'),
    tooltipPosition: 'right',
    run: "click",
},
...stepUtils.searchOrCreateMany2X(
    '.o_field_widget[name="partner_id"] input',
    "customer",
    "Agrolait",
    {
        name: "Agrolait",
        email: "agrolait@example.com",
    }
),
{
    trigger: ".o_field_x2many_list_row_add > button",
    content:  _t('Click here to add some products or services'),
    tooltipPosition: 'top',
    run: 'click',
},
{
    trigger: ".o_sale_order",
},
{
    trigger: '.o_selected_row textarea.o_input',
    content: _t("Select a recurring product"),
    tooltipPosition: "right",
    run: "edit eLearning Access",
},
{
    trigger: 'ul.ui-autocomplete a:contains("eLearning Access")',
    content: _t("Select this product."),
    run: "click",
},
{
    trigger: 'div[name="plan_block"] .o_field_widget[name="plan_id"] input',
    content: _t("Choose the invoice duration for your subscription"),
    run: "edit Monthly",
},
{
    trigger: 'div[name="plan_block"] .o-autocomplete--dropdown-item:contains("Monthly")',
    content: _t("Select this recurring plan."),
    run: "click",
},
{
    trigger: '.o_data_cell[name="product_and_description"]',
    content: _t("Close the recurring plan dropdown."),
    run: "click",
},
{
    trigger: '.o_form_button_save',
    content: _t("Save your subscription."),
    run: "click",
},
{
    trigger: '.o_form_saved, .o_form_readonly',
},

]});
