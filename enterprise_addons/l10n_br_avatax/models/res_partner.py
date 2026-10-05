# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_br_activity_sector = fields.Selection(
        string="Main Activity Sector",
        selection=[
            ("armedForces", "Armed Forces"),
            ("auctioneer", "Auctioneer"),
            ("audiovisualIndustry", "Audiovisual Industry"),
            ("bondedWarehouse", "Bonded Warehouse"),
            ("broadcastingIndustry", "Broadcasting Industry"),
            ("construction", "Construction"),
            ("coops", "Coops"),
            ("distributor", "Distributor"),
            ("distributionCenter", "Distribution Center"),
            ("electricityDistributor", "Electricity Distributor"),
            ("energyGeneration", "Energy Generation"),
            ("extractor", "Extractor"),
            ("farmCoop", "Farm Coop"),
            ("filmIndustry", "Film Industry"),
            ("finalConsumer", "Final Consumer"),
            ("fuelDistributor", "Fuel Distributor"),
            ("generalWarehouse", "General Warehouse"),
            ("importer", "Importer"),
            ("industry", "Industry"),
            ("itaipubiNacional", "Itaipu Binacional"),
            ("maritimeService", "Maritime Service"),
            ("mealSupplier", "Meal Supplier"),
            ("nonProfitEntity", "Non Profit Entity"),
            ("pharmaDistributor", "Pharma Distributor"),
            ("publicAgency", "Public Agency"),
            ("religiousEstablishment", "Religious Establishment"),
            ("retail", "Retail"),
            ("ruralProducer", "Rural Producer"),
            ("securityPublicAgency", "Security Public Agency"),
            ("service", "Service"),
            ("stockWarehouse", "Stock Warehouse"),
            ("telco", "Telco"),
            ("transporter", "Transporter"),
            ("waterDistributor", "Water Distributor"),
            ("wholesale", "Wholesale"),
            ("commerce", "Commerce"),
        ],
        help="Brazil: List of main Activity Sectors of the contact"
    )
    l10n_br_taxpayer = fields.Selection(
        string="ICMS Taxpayer Type",
        selection=[
            ("icms", "ICMS Taxpayer"),
            ("exempt", "Taxpayer Exempt"),
            ("non", "Non-Taxpayer"),
        ],
        help="Brazil: Taxpayer Type informs whether the contact is within the ICMS regime, if it is Exempt, or if it is a Non-Taxpayer"
    )
    l10n_br_tax_regime = fields.Selection(
        string="Tax Regime",
        selection=[
            ("realProfit", "Real Profit"),
            ("estimatedProfit", "Estimated Profit"),
            ("simplified", "Simplified"),
            ("simplifiedOverGrossthreshold", "Simplified over Gross Threshold"),
            ("simplifiedEntrepreneur", "Simplified Entrepreneur"),
            ("notApplicable", "Not Applicable"),
            ("individual", "Individual"),
            ("variable", "Variable"),
        ],
        help="Brazil: Contact FederalTax Regime"
    )
    l10n_br_subject_cofins = fields.Selection(
        [("T", "Taxable"), ("N", "Not Taxable"), ("Z", "Taxable With Rate=0.00"), ("E", "Exempt"), ("H", "Suspended")],
        string="COFINS Details",
        default="T",
        help="Brazil: There are cases where both seller, buyer, and items are taxable but a special situation forces the transaction to be exempt especially "
        "for PIS and COFINS. This attribute allows users to identify such scenarios and trigger the exemption despite all other settings.",
    )
    l10n_br_subject_pis = fields.Selection(
        [("T", "Taxable"), ("N", "Not Taxable"), ("Z", "Taxable With Rate=0.00"), ("E", "Exempt"), ("H", "Suspended")],
        string="PIS Details",
        default="T",
        help="Brazil: There are cases where both seller, buyer, and items are taxable but a special situation forces the transaction to be exempt especially for PIS "
        "and COFINS. This attribute allows users to identify such scenarios and trigger the exemption despite all other settings.",
    )
    l10n_br_is_subject_csll = fields.Boolean(
        "CSLL Taxable",
        default=True,
        help="Brazil: If not checked, then it will be treated as Exempt. There are cases where both seller, buyer, and items are taxable but a special situation "
        "forces the transaction to be CSLL exempt. This attribute allows users to identify such scenarios and trigger the exemption despite "
        "all other settings.",
    )
    l10n_br_iss_simples_rate = fields.Float(
        "ISS Simplified Rate",
        help="Brazil: In case the customer or the seller - company - is in the "
        "Simplified Regime, the seller - company - needs to inform the ISS rate.",
    )

    def l10n_br_action_open_res_partner(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.id,
        }

    def _l10n_br_avatax_action_missing_fields(self):
        """Open the partner(s) with fields missing for Avatax Brazil: the form for a single
        partner, the Brazil-specific list for several."""
        action = {
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "context": {"create": False, "delete": False},
        }
        if len(self) == 1:
            action["res_id"] = self.id
            action["views"] = [(False, "form")]
        else:
            action["name"] = self.env._("Contacts")
            action["domain"] = [("id", "in", self.ids)]
            action["views"] = [(self.env.ref("l10n_br_avatax.res_partner_view_list").id, "list"), (False, "form")]
        return action
