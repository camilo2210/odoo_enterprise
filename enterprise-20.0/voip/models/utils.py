import re
import uuid

try:
    import phonenumbers
    from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
except ImportError:
    phonenumbers = None


INTERNATIONAL_PHONE_NUMBER_RE = re.compile(
    r"""
    ^                           # Start of the string
    (?:\++|00)                  # Match one or more '+' or '00' at the beginning
    (?P<phone_number>[1-9]\d*)  # a non-zero digit followed by any digits
    $                           # End of the string
    """,
    re.VERBOSE,
)


def digits(number):
    return re.sub(r"\D", "", number or "")


def same_number(a, b):
    a, b = digits(a), digits(b)
    if not a or not b:
        return False
    return a == b or (len(a) >= 9 and len(b) >= 9 and a[-9:] == b[-9:])


def is_valid_uuid4(value):
    try:
        return uuid.UUID(str(value)).version == 4
    except ValueError:
        return False


def normalize_caller_number(number):
    n = re.sub(r"\s", "", number or "")
    if n.startswith("+"):
        return n
    if n.startswith("00"):
        return "+" + n[2:]
    if n.isdigit() and len(n) >= 10 and not n.startswith("0"):
        return "+" + n
    return number


def extract_country_code(phone_number):
    if not phonenumbers:
        return {"iso": "", "itu": ""}

    def extract_country_code_from_partial_number(phone_number):
        match = INTERNATIONAL_PHONE_NUMBER_RE.match(phone_number)
        if not match:
            return {"iso": "", "itu": ""}
        sanitized_number = match.group("phone_number")  # the phone number without the + or 00
        for length in range(min(4, len(sanitized_number) + 1), 0, -1):  # 3 is the max length of a country code
            country_code = int(sanitized_number[:length])
            if (
                country_code in COUNTRY_CODE_TO_REGION_CODE
                # Only accept country codes that map to exactly one region
                # (e.g., accept 44->['GB'] for UK, reject 1->['US','CA',...] for North America)
                and len(COUNTRY_CODE_TO_REGION_CODE[country_code]) == 1
            ):
                region_code = phonenumbers.region_code_for_country_code(country_code)
                return {
                    "iso": region_code.lower() if region_code != "ZZ" else "",
                    "itu": str(country_code) if region_code != "ZZ" else "",
                }
        return {"iso": "", "itu": ""}

    phone_number = phone_number.strip()
    # The international call prefix "00" is equivalent to "+"; normalize a leading
    # "00" (only when followed by a country-code digit 1-9, like
    # INTERNATIONAL_PHONE_NUMBER_RE) so phonenumbers can parse the full number and
    # resolve shared country codes by the national number (e.g. 00 1 650… → US,
    # not the ambiguous bare "1"). parse()/region_code_for_number() still validate
    # the result, so a number that isn't actually international falls through.
    parsable_number = re.sub(r"^00(?=[1-9])", "+", phone_number)
    if len(parsable_number) >= 6 and phonenumbers:
        try:
            parsed_number = phonenumbers.parse(parsable_number, None)
            country_code = phonenumbers.region_code_for_number(parsed_number)
            if country_code:
                return {
                    "iso": country_code.lower(),
                    "itu": str(parsed_number.country_code),
                }
        except phonenumbers.NumberParseException:
            pass
    return extract_country_code_from_partial_number(phone_number)
