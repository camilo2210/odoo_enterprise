from odoo import api, models

CODE_TO_EDI_ID = {
    'l10n_fr_fonds_commercial': {
        'brut_round': {'zone': 'AA'},
        'amort_round': {'zone': 'BA'},
        'net_round': {'zone': 'CA'},
    },
    'l10n_fr_autres_incorp': {
        'brut_round': {'zone': 'AB'},
        'amort_round': {'zone': 'BB'},
        'net_round': {'zone': 'CB'},
    },
    'l10n_fr_immobilis_corporelles': {
        'brut_round': {'zone': 'AC'},
        'amort_round': {'zone': 'BC'},
        'net_round': {'zone': 'CC'},
    },
    'l10n_fr_immobilis_fin': {
        'brut_round': {'zone': 'AD'},
        'amort_round': {'zone': 'BD'},
        'net_round': {'zone': 'CD'},
    },
    'l10n_fr_actif_immobilise': {
        'brut_round': {'zone': 'AE'},
        'amort_round': {'zone': 'BE'},
        'net_round': {'zone': 'CE'},
    },
    'l10n_fr_matieres_approvi_cours': {
        'brut_round': {'zone': 'AF'},
        'amort_round': {'zone': 'BF'},
        'net_round': {'zone': 'CF'},
    },
    'l10n_fr_marchandises': {
        'brut_round': {'zone': 'AG'},
        'amort_round': {'zone': 'BG'},
        'net_round': {'zone': 'CG'},
    },
    'l10n_fr_advances_commandes': {
        'brut_round': {'zone': 'AH'},
        'amort_round': {'zone': 'BH'},
        'net_round': {'zone': 'CH'},
    },
    'l10n_fr_creances_rattaches': {
        'brut_round': {'zone': 'AJ'},
        'amort_round': {'zone': 'BJ'},
        'net_round': {'zone': 'CJ'},
    },
    'l10n_fr_autres_creances': {
        'brut_round': {'zone': 'AK'},
        'amort_round': {'zone': 'BK'},
        'net_round': {'zone': 'CK'},
    },
    'l10n_fr_valeurs_placement': {
        'brut_round': {'zone': 'AL'},
        'amort_round': {'zone': 'BL'},
        'net_round': {'zone': 'CL'},
    },
    'l10n_fr_dispo': {
        'brut_round': {'zone': 'AM'},
        'amort_round': {'zone': 'BM'},
        'net_round': {'zone': 'CM'},
    },
    'l10n_fr_charges_avance': {
        'brut_round': {'zone': 'AP'},
        'amort_round': {'zone': 'BP'},
        'net_round': {'zone': 'CP'},
    },
    'l10n_fr_actif_circulant': {
        'brut_round': {'zone': 'AQ'},
        'amort_round': {'zone': 'BQ'},
        'net_round': {'zone': 'CQ'},
    },
    'l10n_fr_actif_tot': {
        'brut_round': {'zone': 'AR'},
        'amort_round': {'zone': 'BR'},
        'net_round': {'zone': 'CR'},
    },
    'l10n_fr_subventions_invest': {
        'net_round': {'zone': 'AS'},
    },
    'l10n_fr_dette_tva': {
        'net_round': {'zone': 'AT'},
    },
    'l10n_fr_dettes_sociales': {
        'net_round': {'zone': 'AU'},
    },
    'l10n_fr_reserve_art': {
        'net_round': {'zone': 'EB'},
    },
    'l10n_fr_compte_assoc': {
        'net_round': {'zone': 'EE'},
    },
    'l10n_fr_capital': {
        'net_round': {'zone': 'FA'},
    },
    'l10n_fr_ecarts_reeval': {
        'net_round': {'zone': 'FB'},
    },
    'l10n_fr_reserve_legale': {
        'net_round': {'zone': 'FC'},
    },
    'l10n_fr_reserve_regl': {
        'net_round': {'zone': 'FD'},
    },
    'l10n_fr_autres_reserves': {
        'net_round': {'zone': 'FE'},
    },
    'l10n_fr_report_nouveau': {
        'net_round': {'zone': 'FF'},
    },
    'l10n_fr_result_exercice': {
        'net_round': {'zone': 'FG'},
    },
    'l10n_fr_provisions_reglement': {
        'net_round': {'zone': 'FH'},
    },
    'l10n_fr_capitaux_propres': {
        'net_round': {'zone': 'FJ'},
    },
    'l10n_fr_provisions_risque_charge': {
        'net_round': {'zone': 'FK'},
    },
    'l10n_fr_emprunts_dettes': {
        'net_round': {'zone': 'FL'},
    },
    'l10n_fr_avances_cours': {
        'net_round': {'zone': 'FM'},
    },
    'l10n_fr_dettes_rattaches': {
        'net_round': {'zone': 'FN'},
    },
    'l10n_fr_autres_dettes': {
        'net_round': {'zone': 'FP'},
    },
    'l10n_fr_produits_davance': {
        'net_round': {'zone': 'FQ'},
    },
    'l10n_fr_dettes': {
        'net_round': {'zone': 'FR'},
    },
    'l10n_fr_passif_tot': {
        'net_round': {'zone': 'FS'},
    },
    'l10n_fr_immo_fin_echeance': {
        'net_round': {'zone': 'HA'},
    },
    'l10n_fr_creance_long': {
        'net_round': {'zone': 'HB'},
    },
    'l10n_fr_compte_cour_assoc': {
        'net_round': {'zone': 'HC'},
    },
    'l10n_fr_dettes_long': {
        'net_round': {'zone': 'JA'},
    },
    'l10n_fr_immo_creees_cours': {
        'net_round': {'zone': 'JB'},
    },
    'l10n_fr_immo_vendues_cours': {
        'net_round': {'zone': 'JC'},
    },
}


class L10nFrReports2033AReportHandler(models.AbstractModel):
    _name = 'l10n_fr_reports.2033.a.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = '2033 A Report Handler'

    @api.model
    def _get_code_to_edi_id(self):
        # Used in the fiscal declaration handler to have all the mapper
        return CODE_TO_EDI_ID
