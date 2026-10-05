# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Doc for UrbanPiper Supported Languages
# https://api-docs.urbanpiper.com/downstream/api/references/supported-languages
URBAN_PIPER_SUPPORTED_LANG = {'hi', 'ar', 'ja', 'pt', 'fr', 'es'}


def get_urbanpiper_translation(field_data):
    """
    Build a language-wise translation payload for UrbanPiper.

    :param dict field_data: A mapping of field names to their corresponding translation records.
        Example: {
            'title': name_field_translations,
            'description': description_field_translations,
        }
    :returns: A list of translation dictionaries grouped by language, formatted for the UrbanPiper API.
        Example output: [
            {'language': 'hi', 'title': 'अच्छा उत्पाद', 'description': 'अच्छा उत्पाद विवरण'},
            {'language': 'fr', 'title': 'bon produit', 'description': 'bonne description du produit'},
        ]
    """

    translations_by_lang = {}
    for field_name, field_translations in field_data.items():
        for translation in field_translations[0]:
            lang_code = translation.get('lang').split('_')[0]
            if lang_code not in URBAN_PIPER_SUPPORTED_LANG:
                continue
            if lang_code not in translations_by_lang:
                translations_by_lang[lang_code] = {
                    'language': lang_code
                }
            translations_by_lang[lang_code][field_name] = translation.get('value')
    return list(translations_by_lang.values())
