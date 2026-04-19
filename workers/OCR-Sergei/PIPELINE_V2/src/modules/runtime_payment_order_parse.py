from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_document_parser_common import (
    choose_best_code_prefixed_text,
    clean_text,
    cleanup_bank_name,
    extract_all_accounts,
    extract_all_bics,
    extract_all_datetimes,
    extract_all_tax_ids,
    extract_bank_account,
    extract_company_names,
    extract_person_name,
    get_regions,
    load_json,
    normalize_leading_code_prefix,
    row_texts,
    to_float,
)
from src.modules.runtime_payment_order_helpers import (
    build_form_text_map,
    enrich_payment_order_result,
    extract_all_po_bics,
    find_first,
    normalize_po_bic_candidate,
    normalize_po_bank_name,
    strip_po_markup,
)


from src.modules.runtime_payment_order_parse_helpers import (
    roi_text,
    y_overlap_len,
    trim_at_anchors,
    extract_form_section,
    split_company_and_address,
    cleanup_po_field,
    extract_purpose_candidates_from_raw,
    normalize_po_company_name,
    normalize_po_bank_name,
    extract_section_bank_name,
    extract_money_words,
    extract_money_words_from_raw,
)
from src.modules.runtime_payment_order_roi_context import PaymentOrderRoiContext

def parse_payment_order(roi_path: Path):
    data = load_json(roi_path)
    regions = get_regions(data)
    form_rois = [r for r in regions if r.get("kind") == "form_roi"]
    lines = [strip_po_markup(r.get("text")) for r in form_rois if strip_po_markup(r.get("text"))]
    ctx = PaymentOrderRoiContext(form_rois, roi_path)




























    full = " ".join([roi_text(r) for r in form_rois if roi_text(r)])
    raw_ocr_items = ctx.load_raw_ocr_items()
    sender_section = extract_form_section(full, r'Банк-отправитель:', (r'Банк-получатель:', r'Бенефициар:', r'Назначение\s+платежа:'))
    receiver_section = extract_form_section(full, r'Банк-получатель:', (r'Бенефициар:', r'Назначение\s+платежа:'))

    number = None
    po_type = None
    title_roi = ctx.find_roi(r'ПЛАТЕЖНОЕ ПОРУЧЕНИЕ')
    if title_roi:
        txt = roi_text(title_roi)
        m = re.search(r'№\s*([0-9]+)\s*\(([^)]+)\)', txt or "", flags=re.I)
        if m:
            number = clean_text(m.group(1))
            po_type = clean_text(m.group(2))

    document_date = None
    date_roi = ctx.find_roi(r'Дата:')
    if date_roi:
        txt = roi_text(date_roi)
        m = re.search(r'Дата:\s*([0-3]?\d\.[01]?\d\.20\d{2})', txt or '', flags=re.I)
        if m:
            document_date = clean_text(m.group(1))
    if not document_date:
        m = re.search(r'Дата:\s*([0-3]?\d\.[01]?\d\.20\d{2})', full)
        document_date = clean_text(m.group(1)) if m else None

    urgent = bool(re.search(r'Срочный\s*Х', full, flags=re.I))
    non_urgent = bool(re.search(r'Несрочный\s*Х', full, flags=re.I))

    payer = {
        "name": None,
        "bank_account": None,
        "bank_code": None,
        "tax_id": None,
        "bank_name": None,
        "address": None,
    }
    payee = {
        "name": None,
        "bank_account": None,
        "bank_code": None,
        "tax_id": None,
        "bank_name": None,
    }


    direct_bank_codes = ctx.extract_ordered_bank_code_values()
    if len(direct_bank_codes) > 0:
        payer["bank_code"] = direct_bank_codes[0]
    if len(direct_bank_codes) > 1:
        payee["bank_code"] = direct_bank_codes[1]

    payer_roi = ctx.find_roi(r'Плательщик:')
    if payer_roi:
        txt = roi_text(payer_roi)
        payload = re.sub(r'^.*?Плательщик\s*:?\s*', '', txt or '', flags=re.I)
        account = None

        m = re.search(r'(BY\d{2}[A-ZА-Я0-9 ]+)\s+Счет\s*№:?\s*$', payload or '', flags=re.I)
        if m:
            account = extract_bank_account(m.group(1))
            payload = clean_text(payload[:m.start()])
        else:
            m = re.search(r'(BY\d{2}[A-ZА-Я0-9 ]+)', payload or '', flags=re.I)
            if m:
                account = extract_bank_account(m.group(1))
                payload = clean_text(payload[:m.start()])

        payload = re.sub(r'\s+Банк-отправитель.*$', '', payload or '', flags=re.I)
        payload = clean_text(payload)

        payer_name, payer_address = split_company_and_address(payload)
        payer["name"] = payer_name
        payer["address"] = payer_address
        payer["bank_account"] = account

        below_roi = ctx.find_below_neighbor(payer_roi)
        if below_roi:
            below_text = clean_text(roi_text(below_roi))
            if below_text and not re.search(r'Банк-|Счет\s*№|Код\s+валюты|Сумма\s+цифрами', below_text, flags=re.I):
                if not payer.get("address"):
                    payer["address"] = below_text
                elif below_text not in payer["address"]:
                    payer["address"] = clean_text(f"{payer['address']} {below_text}")

    if not payer.get("address"):
        payer_section_match = re.search(
            r'Плательщик:\s*(.+?)(?=\s+Банк-отправитель:|\s+Код\s+валюты:|\s+Сумма\s+цифрами:|$)',
            full,
            flags=re.I,
        )
        if payer_section_match:
            payer_section = clean_text(payer_section_match.group(1))
            if payer_section:
                if payer.get("bank_account"):
                    payer_section = payer_section.replace(payer["bank_account"], ' ')
                payer_section = re.sub(r'BY\d{2}[A-ZА-Я0-9 ]+', ' ', payer_section, flags=re.I)
                payer_section = re.sub(r'\bСчет\s*№:?\s*$', ' ', payer_section, flags=re.I)
                payer_section = clean_text(payer_section)
                payer_name, payer_address = split_company_and_address(payer_section)
                if payer_name and not payer.get("name"):
                    payer["name"] = payer_name
                if payer_address:
                    payer["address"] = payer_address

    sender_roi = ctx.find_roi(r'Банк-отправитель:')
    if sender_roi:
        row_text = ctx.collect_same_row_text(sender_roi)
        txt = row_text or roi_text(sender_roi)
        section_name = extract_section_bank_name(sender_section, r'Банк-отправитель')
        if section_name:
            payer["bank_name"] = section_name
        else:
            m = re.search(r'Банк-отправитель:?\s*(.+?)(?=\s+Счет\s*№|\s+Код\s+банка:|$)', txt or '', flags=re.I)
            if m:
                payer["bank_name"] = normalize_po_bank_name(m.group(1))

        code_label_roi = ctx.find_matching_label_roi(sender_roi, r"\u041a\u043e\u0434\s+\u0431\u0430\u043d\u043a\u0430:")
        code = ctx.extract_bic_from_label_roi(code_label_roi)
        code = code or ctx.extract_section_bank_code(sender_section) or ctx.extract_bic_after_label(txt) or ctx.extract_bic_from_row(sender_roi)
        if code and not payer.get("bank_code"):
            payer["bank_code"] = code

    receiver_roi = ctx.find_roi(r'Банк-получатель:')
    if receiver_roi:
        row_text = ctx.collect_same_row_text(receiver_roi)
        txt = row_text or roi_text(receiver_roi)
        section_name = extract_section_bank_name(receiver_section, r'Банк-получатель')
        if section_name:
            payee["bank_name"] = section_name
        else:
            m = re.search(r'Банк-получатель:?\s*(.+?)(?=\s+Счет\s*№|\s+Код\s+банка:|$)', txt or '', flags=re.I)
            if m:
                payee["bank_name"] = normalize_po_bank_name(m.group(1))

        code_label_roi = ctx.find_matching_label_roi(receiver_roi, r"\u041a\u043e\u0434\s+\u0431\u0430\u043d\u043a\u0430:")
        code = ctx.extract_bic_from_label_roi(code_label_roi)
        code = code or ctx.extract_section_bank_code(receiver_section) or ctx.extract_bic_after_label(txt) or ctx.extract_bic_from_row(receiver_roi)
        if code and not payee.get("bank_code"):
            payee["bank_code"] = code

    beneficiary_roi = ctx.find_roi(r'Бенефициар:')
    if beneficiary_roi:
        txt = roi_text(beneficiary_roi)
        payload = re.sub(r'^Бенефициар\s*:?\s*', '', txt or '', flags=re.I)
        account = None
        m = re.search(r'\s+Счет\s*№:?\s*(BY\d{2}[A-ZА-Я0-9 ]+)', payload or '', flags=re.I)
        if m:
            account = extract_bank_account(m.group(1))
            payload = clean_text(payload[:m.start()])
        payee["name"] = normalize_po_company_name(payload)
        payee["bank_account"] = account

    payer["tax_id"] = None
    payee["tax_id"] = None

    payment_priority = None
    queue_roi = ctx.find_roi(r'\bОчередь\b')
    if queue_roi:
        payment_priority = ctx.extract_payment_priority_from_queue(queue_roi)

    amount_in_words = extract_money_words_from_raw(raw_ocr_items)
    currency_code = None
    amount = None

    amount_words_roi = ctx.find_roi(r'Сумма\s+и\s+валюта:')
    if amount_words_roi and amount_in_words is None:
        txt = roi_text(amount_words_roi)
        m = re.search(r'^Сумма и валюта:\s*(.+)$', txt or '', flags=re.I)
        if m:
            amount_in_words = extract_money_words(m.group(1))

    currency_label_roi = ctx.find_roi(r'Код\s+валюты:')
    if currency_label_roi:
        currency_value = ctx.extract_value_after_label_from_row(currency_label_roi, r'Код\s+валюты:?\s*', r'(\d{3})')
        if currency_value:
            currency_code = clean_text(currency_value)
        else:
            currency_value_roi = ctx.find_right_neighbor(currency_label_roi, max_gap=220)
            if currency_value_roi:
                currency_code = clean_text(roi_text(currency_value_roi))
    if currency_code is None:
        m = re.search(r'Код\s+валюты:\s*(\d{3})', full, flags=re.I)
        if m:
            currency_code = clean_text(m.group(1))

    amount_label_roi = ctx.find_amount_label_roi()
    if amount_label_roi:
        amount_value = ctx.extract_value_after_label_from_row(amount_label_roi, r'Сумма\s+[А-Яа-яA-Za-z]{4,12}:?\s*', r'([0-9][0-9\s,\.]+)')
        if amount_value:
            amount = to_float(amount_value)
        else:
            amount_value_roi = ctx.find_right_neighbor(amount_label_roi, max_gap=420)
            if amount_value_roi:
                amount = to_float(roi_text(amount_value_roi))
    if amount is None:
        matches = re.finditer(r'Сумма\s+[А-Яа-яA-Za-z]{4,12}:\s*([0-9][0-9\s,\.]+)', full, flags=re.I)
        for match in matches:
            whole = match.group(0)
            if re.search(r'валют|перевод', whole, flags=re.I):
                continue
            amount = to_float(match.group(1))
            if amount is not None:
                break

    if amount_in_words is None:
        m = re.search(
            r'Сумма и валюта:\s*(.+?)(?=\s+Плательщик:|\s+Код\s+валюты:|\s+Сумма\s+цифрами:|\s+Банк-отправитель:|$)',
            full,
            flags=re.I,
        )
        if m:
            amount_in_words = extract_money_words(m.group(1))

    if currency_code is None or amount is None:
        m = re.search(
            r'Сумма и валюта:\s*(.+?)\s+Код\s+валюты:\s*(\d+)\s+Сумма\s+цифрами:\s*([0-9,\.]+)',
            full,
            flags=re.I,
        )
        if m:
            if amount_in_words is None:
                amount_in_words = extract_money_words(m.group(1))
            if currency_code is None:
                currency_code = clean_text(m.group(2))
            if amount is None:
                amount = to_float(m.group(3))


    purpose_candidates = []
    purpose = None
    purpose_roi = ctx.find_roi(r'\u041d\u0430\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435\s+\u043f\u043b\u0430\u0442\u0435\u0436\u0430:')
    if purpose_roi:
        txt = roi_text(purpose_roi)
        m = re.search(r'^\u041d\u0430\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435 \u043f\u043b\u0430\u0442\u0435\u0436\u0430:\s*(.+)$', txt or '', flags=re.I)
        if m:
            value = clean_text(m.group(1))
            if value:
                purpose_candidates.append(value)
    if not purpose_candidates:
        m = re.search(r'\u041d\u0430\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435 \u043f\u043b\u0430\u0442\u0435\u0436\u0430:\s*(.+?)\s+\u2116 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430:', full, flags=re.I)
        if m:
            value = clean_text(m.group(1))
            if value:
                purpose_candidates.append(value)

    purpose_candidates.extend(extract_purpose_candidates_from_raw(raw_ocr_items))
    purpose = choose_best_code_prefixed_text(*purpose_candidates)
    if not purpose:
        purpose = next((clean_text(v) for v in purpose_candidates if clean_text(v)), None)
        if purpose:
            purpose = normalize_leading_code_prefix(purpose)

    receipt_date = None
    execution_date = None
    executing_bank = None
    status = None

    bank_exec_roi = ctx.find_roi(r'Дата исполнения')
    if bank_exec_roi:
        txt = roi_text(bank_exec_roi)
        if txt:
            m = re.search(r'Дата исполнения:?\s*([0-3]?\d\.[01]?\d\.20\d{2}\s+\d{2}:\d{2})', txt, flags=re.I)
            if m:
                execution_date = clean_text(m.group(1))
                status = "исполнено"

            m = re.search(r'Дата поступления:?\s*([0-3]?\d\.[01]?\d\.20\d{2}\s+\d{2}:\d{2})', txt, flags=re.I)
            if m:
                receipt_date = clean_text(m.group(1))

    executing_bank = ctx.extract_executing_bank_from_stamp() or executing_bank

    signatory = {"position": None, "name": None}
    signatory["name"] = ctx.extract_signatory_from_block()
    if not signatory.get("name"):
        m = re.search(r'([А-Яа-яA-Za-z ]+)\s+([А-ЯЁA-Z][а-яё]+\s+[А-ЯЁA-Z][а-яё]+\s+[А-ЯЁA-Z][а-яё]+)$', full)
        if m:
            candidate_name = clean_text(m.group(2))
            if candidate_name and 'Код' not in candidate_name:
                signatory["position"] = clean_text(m.group(1))
                signatory["name"] = candidate_name

    file_key = roi_path.name.replace("_roi_text.json", ".pdf")
    return enrich_payment_order_result({
        "payment_order": {
            file_key: {
                "payment_order_number": number,
                "payment_order_type": po_type,
                "document_date": document_date,
                "urgent": urgent,
                "non_urgent": non_urgent,
                "payer": payer,
                "payee": payee,
                "payment_details": {
                    "amount": amount,
                    "currency_code": currency_code,
                    "currency": "BYN",
                    "currency_full": "белорусские рубли" if amount_in_words else None,
                    "amount_in_words": amount_in_words,
                    "purpose": purpose,
                    "payment_priority": payment_priority,
                },
                "execution_details": {
                    "receipt_date": receipt_date,
                    "execution_date": execution_date,
                    "executing_bank": executing_bank,
                    "status": status,
                },
                "signatory": signatory,
            }
        }
    }, lines, full)
