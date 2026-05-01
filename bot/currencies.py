"""Curated list of fiat currencies supported by Bybit P2P.

The list is hardcoded because Bybit does not expose a public endpoint
that returns the full set. Refresh manually if Bybit adds new currencies.

Flags are generated from the ISO 3166-1 alpha-2 country code via the
regional-indicator-symbol Unicode trick — no need to type emoji by hand.
"""

# Currency → primary country (ISO 3166-1 alpha-2)
CURRENCY_TO_COUNTRY: dict[str, str] = {
    "AED": "AE", "AMD": "AM", "ARS": "AR", "AUD": "AU", "AZN": "AZ",
    "BAM": "BA", "BDT": "BD", "BGN": "BG", "BHD": "BH", "BOB": "BO",
    "BRL": "BR", "BYN": "BY",
    "CAD": "CA", "CHF": "CH", "CLP": "CL", "CNY": "CN", "COP": "CO",
    "CRC": "CR", "CZK": "CZ",
    "DKK": "DK", "DOP": "DO", "DZD": "DZ",
    "EGP": "EG", "EUR": "EU",
    "GBP": "GB", "GEL": "GE", "GHS": "GH", "GTQ": "GT",
    "HKD": "HK", "HUF": "HU",
    "IDR": "ID", "ILS": "IL", "INR": "IN", "IQD": "IQ",
    "JOD": "JO", "JPY": "JP",
    "KES": "KE", "KGS": "KG", "KHR": "KH", "KRW": "KR", "KWD": "KW", "KZT": "KZ",
    "LBP": "LB", "LKR": "LK",
    "MAD": "MA", "MDL": "MD", "MKD": "MK", "MMK": "MM", "MNT": "MN",
    "MXN": "MX", "MYR": "MY",
    "NGN": "NG", "NOK": "NO", "NPR": "NP", "NZD": "NZ",
    "OMR": "OM",
    "PEN": "PE", "PHP": "PH", "PKR": "PK", "PLN": "PL",
    "QAR": "QA",
    "RON": "RO", "RSD": "RS", "RUB": "RU",
    "SAR": "SA", "SEK": "SE", "SGD": "SG",
    "THB": "TH", "TJS": "TJ", "TND": "TN", "TRY": "TR", "TWD": "TW",
    "UAH": "UA", "USD": "US", "UYU": "UY", "UZS": "UZ",
    "VES": "VE", "VND": "VN",
    "YER": "YE",
    "ZAR": "ZA",
}

# Sorted alphabetically — same order users will see in the picker
CURRENCIES: list[str] = sorted(CURRENCY_TO_COUNTRY.keys())


def currency_flag(currency_id: str) -> str:
    """Return the flag emoji for a currency code, or 💱 if unknown."""
    country = CURRENCY_TO_COUNTRY.get(currency_id)
    if country is None or len(country) != 2:
        return "💱"
    return "".join(chr(ord(c) - ord("A") + 0x1F1E6) for c in country.upper())
