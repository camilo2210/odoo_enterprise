<?xml version="1.0" encoding="utf-8"?>
<odoo auto_sequence="1">
    <record id="l10n_fr_2033_E" model="account.report">
        <field name="name">2033 E</field>
        <field name="name@fr">2033 E</field>
        <field name="custom_handler_model_id" ref="model_l10n_fr_reports_2033_e_report_handler"/>
        <field name="column_ids">
            <record id="l10n_fr_2033_E_balance_column" model="account.report.column">
                <field name="name">Balance</field>
                <field name="expression_label">balance</field>
            </record>
        </field>
        <field name="line_ids">
            <record id="l10n_fr_2033_E_title" model="account.report.line">
                <field name="name">Added value</field>
                <field name="name@fr">Valeur ajoutée</field>
            </record>
            <record id="l10n_fr_2033_E_1" model="account.report.line">
                <field name="name">Declaration of workforce numbers</field>
                <field name="name@fr">Déclaration des effectifs</field>
                <field name="code">FR_2033_E_workforce</field>
                <field name="expression_ids">
                    <record id="l10n_fr_2033_E_1_expr" model="account.report.expression">
                        <field name="label">balance</field>
                        <field name="engine">aggregation</field>
                        <field name="formula">FR_2033_E_376.balance + FR_2033_E_861.balance</field>
                        <field name="figure_type">integer</field>
                    </record>
                </field>
                <field name="children_ids">
                    <record id="l10n_fr_2033_E_1_1" model="account.report.line">
                        <field name="name">Average number of staff</field>
                        <field name="name@fr">Effectif moyen du personnel</field>
                        <field name="code">FR_2033_E_376</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_1_1_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">external</field>
                                <field name="formula">most_recent</field>
                                <field name="date_scope">from_beginning</field>
                                <field name="subformula">editable;rounding=0</field>
                                <field name="figure_type">integer</field>
                            </record>
                        </field>
                        <field name="children_ids">
                            <record id="l10n_fr_2033_E_1_1_1" model="account.report.line">
                                <field name="name">Of which apprentices</field>
                                <field name="name@fr">Dont apprentis</field>
                                <field name="code">FR_2033_E_657</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_1_1_1_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="figure_type">integer</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_1_1_2" model="account.report.line">
                                <field name="name">Of which disabled</field>
                                <field name="name@fr">Dont handicapés</field>
                                <field name="code">FR_2033_E_651</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_1_1_2_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="figure_type">integer</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_1_2" model="account.report.line">
                        <field name="name">Workforce assigned to craft activities</field>
                        <field name="name@fr">Effectifs affectés à l'activité artisanale</field>
                        <field name="code">FR_2033_E_861</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_1_2_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">external</field>
                                <field name="formula">most_recent</field>
                                <field name="date_scope">from_beginning</field>
                                <field name="figure_type">integer</field>
                                <field name="subformula">editable;rounding=0</field>
                            </record>
                        </field>
                    </record>
                </field>
            </record>
            <record id="l10n_fr_2033_E_2" model="account.report.line">
                <field name="name">Calculation of added value</field>
                <field name="name@fr">Calcul de la valeur ajoutée</field>
                <field name="code">FR_2033_E_calculation_added_value</field>
                <field name="expression_ids">
                    <record id="l10n_fr_2033_E_2_expr" model="account.report.expression">
                        <field name="label">balance</field>
                        <field name="engine">aggregation</field>
                        <field name="formula">FR_2033_E_I.balance + FR_2033_E_II.balance</field>
                    </record>
                </field>
                <field name="children_ids">
                    <record id="l10n_fr_2033_E_2_1" model="account.report.line">
                        <field name="name">I – Reference Turnover CVAE</field>
                        <field name="name@fr">I – Chiffre d'affaires de référence CVAE</field>
                        <field name="code">FR_2033_E_I</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_2_1_5_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">aggregation</field>
                                <field name="formula">FR_2033_E_108.balance + FR_2033_E_118.balance + FR_2033_E_119.balance + FR_2033_E_105.balance</field>
                            </record>
                        </field>
                        <field name="children_ids">
                            <record id="l10n_fr_2033_E_2_1_1" model="account.report.line">
                                <field name="name">Sales of manufactured goods, services and merchandise</field>
                                <field name="name@fr">Ventes de produits fabriqués, prestations de services et marchandises</field>
                                <field name="code">FR_2033_E_108</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_1_1_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_1_2" model="account.report.line">
                                <field name="name">Royalties for concessions, patents, licenses</field>
                                <field name="name@fr">Redevances pour concessions, brevets, licences et assimilées</field>
                                <field name="code">FR_2033_E_118</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_1_2_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_1_3" model="account.report.line">
                                <field name="name">Capital gains on disposal of assets (normal activity)</field>
                                <field name="name@fr">Plus-values de cession d'immobilisations... (activité normale)</field>
                                <field name="code">FR_2033_E_119</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_1_3_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_1_4" model="account.report.line">
                                <field name="name">Rebilling of costs in expense transfer accounts</field>
                                <field name="name@fr">Refacturations de frais inscrites au compte de transfert de charges</field>
                                <field name="code">FR_2033_E_105</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_1_4_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_2_2" model="account.report.line">
                        <field name="name">II – Other products for the calculation of added value</field>
                        <field name="name@fr">II – Autres produits à retenir pour le calcul de la valeur ajoutée</field>
                        <field name="code">FR_2033_E_II</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_2_2_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">aggregation</field>
                                <field name="formula">FR_2033_E_115.balance + FR_2033_E_143.balance + FR_2033_E_113.balance + FR_2033_E_111.balance + FR_2033_E_116.balance + FR_2033_E_153.balance</field>
                            </record>
                        </field>
                        <field name="children_ids">
                            <record id="l10n_fr_2033_E_2_2_1" model="account.report.line">
                                <field name="name">Other current management products (excluding shares of income from joint operations)</field>
                                <field name="name@fr">Autres produits de gestion courante (hors quotes-parts de résultat sur opérations faites en commun)</field>
                                <field name="code">FR_2033_E_115</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_2_1_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_2_2" model="account.report.line">
                                <field name="name">Capitalized production limited to the deductible expenses that contributed to its formation</field>
                                <field name="name@fr">Production immobilisée à hauteur des seules charges déductibles ayant concouru à sa formation</field>
                                <field name="code">FR_2033_E_143</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_2_2_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_2_3" model="account.report.line">
                                <field name="name">Operating subsidies received</field>
                                <field name="name@fr">Subventions d'exploitation reçues</field>
                                <field name="code">FR_2033_E_113</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_2_3_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_2_4" model="account.report.line">
                                <field name="name">Positive variation of stocks</field>
                                <field name="name@fr">Variation positive des stocks</field>
                                <field name="code">FR_2033_E_111</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_2_4_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_2_5" model="account.report.line">
                                <field name="name">Transfer of deductible charges</field>
                                <field name="name@fr">Transferts de charges déductibles de la valeur ajoutée</field>
                                <field name="code">FR_2033_E_116</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_2_5_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_2_6" model="account.report.line">
                                <field name="name">Recoveries on written-off receivables when they are recognized in operating income</field>
                                <field name="name@fr">Rentrées sur créances amorties lorsqu'elles se rapportent au résultat d'exploitation</field>
                                <field name="code">FR_2033_E_153</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_2_6_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_2_3" model="account.report.line">
                        <field name="name">III – Charges to be retained for the calculation of added value</field>
                        <field name="name@fr">III – Charges à retenir pour le calcul de la valeur ajoutée</field>
                        <field name="code">FR_2033_E_III</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_2_3_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">aggregation</field>
                                <field name="formula">FR_2033_E_121.balance + FR_2033_E_145.balance + FR_2033_E_125.balance + FR_2033_E_310.balance + FR_2033_E_133.balance + FR_2033_E_148.balance + FR_2033_E_128.balance + FR_2033_E_135.balance + FR_2033_E_150.balance</field>
                            </record>
                        </field>
                        <field name="children_ids">
                            <record id="l10n_fr_2033_E_2_3_1" model="account.report.line">
                                <field name="name">Purchases</field>
                                <field name="name@fr">Achats</field>
                                <field name="code">FR_2033_E_121</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_3_1_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_3_2" model="account.report.line">
                                <field name="name">Negative variation of stocks</field>
                                <field name="name@fr">Variation négative des stocks</field>
                                <field name="code">FR_2033_E_145</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_3_2_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_3_3" model="account.report.line">
                                <field name="name">External services (excluding rent/royalties)</field>
                                <field name="name@fr">Services extérieurs, à l'exception des loyers et des redevances</field>
                                <field name="code">FR_2033_E_125</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_3_3_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_3_4" model="account.report.line">
                                <field name="name">Rent and fees, except for those related to tangible fixed assets made available under a lease-management agreement, a finance lease agreement, or a lease agreement with a term of more than 6 months</field>
                                <field name="name@fr">Loyers et redevances, à l'exception de ceux afférents à des immobilisations corporelles mises à disposition dans le cadre d'une convention de location-gérance ou de crédit-bail ou encore d'une convention de location de plus de 6 mois</field>
                                <field name="code">FR_2033_E_310</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_3_4_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_3_5" model="account.report.line">
                                <field name="name">Deductible taxes</field>
                                <field name="name@fr">Taxes déductibles de la valeur ajoutée</field>
                                <field name="code">FR_2033_E_133</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_3_5_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_3_6" model="account.report.line">
                                <field name="name">Other current management charges</field>
                                <field name="name@fr">Autres charges de gestion courante (hors quotes-parts de résultat sur opérations faites en commun)</field>
                                <field name="code">FR_2033_E_148</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_3_6_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_3_7" model="account.report.line">
                                <field name="name">Expenses deductible from the value added attributable to reported capitalized production</field>
                                <field name="name@fr">Charges déductibles de la valeur ajoutée afférente à la production immobilisée déclarée</field>
                                <field name="code">FR_2033_E_128</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_3_7_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_3_8" model="account.report.line">
                                <field name="name">The portion of depreciation expenses related to tangible fixed assets made available under a lease-management agreement, a finance lease agreement, or a lease agreement with a term of more than six months that is deductible from gross income</field>
                                <field name="name@fr">Fraction déductible de la valeur ajoutée des dotations aux amortissements afférentes à des immobilisations corporelles mises à disposition dans le cadre d'une convention de location-gérance ou de crédit-bail ou encore d'une convention de location de plus de 6 mois</field>
                                <field name="code">FR_2033_E_135</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_3_8_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                            <record id="l10n_fr_2033_E_2_3_9" model="account.report.line">
                                <field name="name">Capital losses on the disposal of tangible or intangible fixed assets, provided they are related to normal, day-to-day operations</field>
                                <field name="name@fr">Moins-values de cession d'immobilisations corporelles ou incorporelles si rattachées à une activité normale et courante</field>
                                <field name="code">FR_2033_E_150</field>
                                <field name="expression_ids">
                                    <record id="l10n_fr_2033_E_2_3_9_expr" model="account.report.expression">
                                        <field name="label">balance</field>
                                        <field name="engine">external</field>
                                        <field name="formula">most_recent</field>
                                        <field name="date_scope">from_beginning</field>
                                        <field name="subformula">editable;rounding=0</field>
                                    </record>
                                </field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_2_4" model="account.report.line">
                        <field name="name">IV – Value added produced</field>
                        <field name="name@fr">IV – Valeur ajoutée produite</field>
                        <field name="code">FR_2033_E_IV</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_2_4_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">aggregation</field>
                                <field name="formula">FR_2033_E_I.balance + FR_2033_E_II.balance - FR_2033_E_III.balance</field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_2_5" model="account.report.line">
                        <field name="name">V – Contribution on the added value of companies</field>
                        <field name="name@fr">V – Cotisation sur la valeur ajoutée des entreprises</field>
                        <field name="code">FR_2033_E_V</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_2_5_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">external</field>
                                <field name="formula">most_recent</field>
                                <field name="date_scope">from_beginning</field>
                                <field name="subformula">editable;rounding=0</field>
                            </record>
                        </field>
                    </record>
                </field>
            </record>
            <record id="l10n_fr_2033_E_3" model="account.report.line">
                <field name="name">Framework reserved for single establishments within the meaning of the CVAE</field>
                <field name="name@fr">Cadre réservé au mono-établissement au sens de la CVAE</field>
                <field name="code">FR_2033_E_single_establishments</field>
                <field name="children_ids">
                    <record id="l10n_fr_2033_E_3_1" model="account.report.line">
                        <field name="name">Single establishment within the meaning of the CVAE</field>
                        <field name="name@fr">Mono-établissement au sens de la CVAE</field>
                        <field name="code">FR_2033_E_020</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_3_1_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">external</field>
                                <field name="formula">most_recent</field>
                                <field name="date_scope">from_beginning</field>
                                <field name="subformula">editable;rounding=0</field>
                                <field name="figure_type">boolean</field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_3_2" model="account.report.line">
                        <field name="name">CVAE reference turnover (carry over from line 106)</field>
                        <field name="name@fr">Chiffre d'affaires de référence CVAE (report de la ligne 106, le cas échéant ajusté à 12 mois)</field>
                        <field name="code">FR_2033_E_022</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_3_2_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">external</field>
                                <field name="formula">most_recent</field>
                                <field name="date_scope">from_beginning</field>
                                <field name="subformula">editable;rounding=0</field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_3_3" model="account.report.line">
                        <field name="name">Workforce within the meaning of the CVAE</field>
                        <field name="name@fr">Effectifs au sens de la CVAE</field>
                        <field name="code">FR_2033_E_023</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_3_3_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">external</field>
                                <field name="formula">most_recent</field>
                                <field name="date_scope">from_beginning</field>
                                <field name="subformula">editable;rounding=0</field>
                                <field name="figure_type">integer</field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_3_4" model="account.report.line">
                        <field name="name">Revenue of the economic group (companies meeting the ownership requirements set forth in Article 223 A of the French General Tax Code)</field>
                        <field name="name@fr">Chiffre d'affaires du groupe économique (entreprises répondant aux conditions de détention fixées à l'article 223 A du CGI)</field>
                        <field name="code">FR_2033_E_026</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_3_4_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">external</field>
                                <field name="formula">most_recent</field>
                                <field name="date_scope">from_beginning</field>
                                <field name="subformula">editable;rounding=0</field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_3_5" model="account.report.line">
                        <field name="name">Reference period - Start</field>
                        <field name="name@fr">Période de référence - Début</field>
                        <field name="code">FR_2033_E_024</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_3_5_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">external</field>
                                <field name="formula">most_recent</field>
                                <field name="date_scope">from_beginning</field>
                                <field name="subformula">editable;rounding=0</field>
                                <field name="figure_type">date</field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_3_6" model="account.report.line">
                        <field name="name">Reference period - End</field>
                        <field name="name@fr">Période de référence - Fin</field>
                        <field name="code">FR_2033_E_016</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_3_6_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">external</field>
                                <field name="formula">most_recent</field>
                                <field name="date_scope">from_beginning</field>
                                <field name="subformula">editable;rounding=0</field>
                                <field name="figure_type">date</field>
                            </record>
                        </field>
                    </record>
                    <record id="l10n_fr_2033_E_3_7" model="account.report.line">
                        <field name="name">Date of termination</field>
                        <field name="name@fr">Date de cessation</field>
                        <field name="code">FR_2033_E_termination_date</field>
                        <field name="expression_ids">
                            <record id="l10n_fr_2033_E_3_7_expr" model="account.report.expression">
                                <field name="label">balance</field>
                                <field name="engine">external</field>
                                <field name="formula">most_recent</field>
                                <field name="date_scope">from_beginning</field>
                                <field name="subformula">editable;rounding=0</field>
                                <field name="figure_type">date</field>
                            </record>
                        </field>
                    </record>
                </field>
            </record>
        </field>
    </record>
</odoo>
