"""Constants and key hints for prediction normalization."""

MONTHS = {
    "января": "01",
    "февраля": "02",
    "марта": "03",
    "апреля": "04",
    "мая": "05",
    "июня": "06",
    "июля": "07",
    "августа": "08",
    "сентября": "09",
    "октября": "10",
    "ноября": "11",
    "декабря": "12",
}

NUMERIC_KEY_HINTS = {
    "amount",
    "price",
    "cost",
    "cost_with_vat",
    "quantity_total",
    "cost_total",
    "vat_total",
    "cost_with_vat_total",
    "free_unit_price_excl_vat",
    "extra_charge",
    "unit_price_excl_vat",
    "total_excl_vat",
    "total_incl_vat",
    "subtotal_excl_vat",
    "subtotal_no_disc_incl_vat",
    "total_disc_amount",
    "subtotal_with_disc_excl_vat",
    "vat_amount",
    "total_with_disc_incl_vat",
    "amount_no_disc_incl_vat",
    "disc_amount",
    "amount_with_disc_excl_vat",
    "unit_price_incl_vat",
}

INT_KEY_HINTS = {
    "line_number",
    "quantity",
    "total_quantity",
    "quantity_total",
}

BOOL_KEY_HINTS = {
    "urgent",
    "non_urgent",
    "is_valid",
}

DATE_KEY_HINTS = {
    "document_date",
    "invoice_date",
    "date",
    "contract_date",
    "receipt_date",
    "execution_date",
    "valid_until",
}

PERCENT_KEY_HINTS = {
    "vat_rate",
}

ACCOUNT_KEYS = {
    "bank_account",
    "account",
}

CODE_KEYS = {
    "tax_id",
    "kpp",
    "bic",
    "bank_code",
    "barcode",
    "sku",
}

ADDRESS_KEYS = {
    "address",
    "bank_address",
}

BANK_NAME_KEYS = {
    "bank_name",
    "executing_bank",
}

MONEY_WORD_KEYS = {
    "amount_in_words",
    "total_in_words",
    "vat_total_words",
    "cost_with_vat_total_words",
}

FREE_TEXT_KEYS = {
    "note",
    "notes",
    "purpose",
    "basis",
    "warning",
    "publisher",
    "released_by",
    "handed_by",
    "accepted_for_delivery",
    "received_by",
    "documents_transferred",
    "status_note",
    "payment_order_type",
    "currency",
    "currency_full",
    "status",
    "document_type",
    "document_series",
    "document_number",
    "invoice_number",
    "payment_deadline",
    "contract_number",
    "contract_type",
    "article",
}

PARTY_BLOCK_KEYS = {
    "supplier",
    "customer",
    "payer",
    "payee",
    "sender",
    "receiver",
    "signatory",
}

VISUAL_QUOTES_MAP = str.maketrans({
    "«": '"',
    "»": '"',
    "“": '"',
    "”": '"',
    "„": '"',
    "’": "'",
    "‘": "'",
})

REVIEW_FIELD_MARKER = "проверить поле"

CYR_TO_LAT_MAP = str.maketrans({
    "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K",
    "М": "M", "О": "O", "Р": "P", "Т": "T", "У": "Y", "Х": "X",
    "І": "I", "Ү": "Y",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
})
