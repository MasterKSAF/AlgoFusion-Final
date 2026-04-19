from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_document_parser_common import (
    clean_text,
    extract_all_bics,
    extract_company_names,
    extract_person_name,
    load_json,
)
from src.modules.runtime_payment_order_helpers import normalize_po_bic_candidate, strip_po_markup
from src.modules.runtime_payment_order_parse_helpers import cleanup_po_field, roi_text, y_overlap_len


class PaymentOrderRoiContext:
    def __init__(self, form_rois, roi_path: Path):
        self.form_rois = form_rois
        self.roi_path = roi_path

    def find_roi(self, pattern):
        for roi in self.form_rois:
            txt = roi_text(roi)
            if txt and re.search(pattern, txt, flags=re.I):
                return roi
        return None

    def find_all_rois(self, pattern):
        out = []
        for roi in self.form_rois:
            txt = roi_text(roi)
            if txt and re.search(pattern, txt, flags=re.I):
                out.append(roi)
        return out

    def find_right_neighbor(self, base_roi, *, min_overlap_ratio=0.35, max_gap=260):
        bx1, by1, bx2, by2 = base_roi["bbox"]
        base_h = max(1, by2 - by1)
        best = None
        best_score = None

        for roi in self.form_rois:
            if roi["id"] == base_roi["id"]:
                continue

            txt = roi_text(roi)
            if not txt:
                continue

            rx1, ry1, rx2, ry2 = roi["bbox"]
            gap = rx1 - bx2
            if gap < -10 or gap > max_gap:
                continue

            overlap = y_overlap_len(base_roi["bbox"], roi["bbox"])
            if overlap < min(base_h, max(1, ry2 - ry1)) * min_overlap_ratio:
                continue

            score = (max(0, gap), abs(ry1 - by1), abs((ry2 - ry1) - base_h))
            if best_score is None or score < best_score:
                best_score = score
                best = roi

        return best

    def find_below_neighbor(self, base_roi, *, min_x_overlap_ratio=0.45, max_gap=140):
        bx1, by1, bx2, by2 = base_roi["bbox"]
        base_w = max(1, bx2 - bx1)
        best = None
        best_score = None

        for roi in self.form_rois:
            if roi["id"] == base_roi["id"]:
                continue

            txt = roi_text(roi)
            if not txt:
                continue

            rx1, ry1, rx2, ry2 = roi["bbox"]
            gap = ry1 - by2
            if gap < -5 or gap > max_gap:
                continue

            x_overlap = max(0, min(bx2, rx2) - max(bx1, rx1))
            if x_overlap < base_w * min_x_overlap_ratio:
                continue

            score = (max(0, gap), abs(rx1 - bx1), abs((rx2 - rx1) - base_w))
            if best_score is None or score < best_score:
                best_score = score
                best = roi

        return best

    def collect_same_row_text(self, base_roi, *, min_overlap_ratio=0.35, x_pad_left=20, x_pad_right=1200):
        bx1, by1, bx2, by2 = base_roi["bbox"]
        base_h = max(1, by2 - by1)
        row = []
        seen = set()
        for roi in self.form_rois:
            txt = roi_text(roi)
            if not txt:
                continue
            rx1, ry1, rx2, ry2 = roi["bbox"]
            if rx2 < bx1 - x_pad_left or rx1 > bx2 + x_pad_right:
                continue
            overlap = y_overlap_len(base_roi["bbox"], roi["bbox"])
            if overlap < min(base_h, max(1, ry2 - ry1)) * min_overlap_ratio:
                continue
            if roi["id"] in seen:
                continue
            seen.add(roi["id"])
            row.append((rx1, txt))
        row.sort(key=lambda item: item[0])
        return clean_text(" ".join(text for _x, text in row if text))

    def extract_value_after_label_from_row(self, base_roi, label_pattern, value_pattern):
        row_text = strip_po_markup(self.collect_same_row_text(base_roi))
        if not row_text:
            return None
        label_match = re.search(label_pattern, row_text, flags=re.I)
        if not label_match:
            return None
        tail = clean_text(row_text[label_match.end():])
        if not tail:
            return None
        value_match = re.search(value_pattern, tail, flags=re.I)
        if not value_match:
            return None
        return clean_text(value_match.group(1) if value_match.groups() else value_match.group(0))

    def find_amount_label_roi(self):
        exact = self.find_roi(r'Сумма\s+цифрами:')
        if exact:
            return exact

        candidates = []
        for roi in self.form_rois:
            txt = roi_text(roi)
            if not txt:
                continue
            if not re.search(r'^Сумма\s+[А-Яа-яA-Za-z]{4,12}:$', txt, flags=re.I):
                continue
            if re.search(r'валют|перевод', txt, flags=re.I):
                continue
            bbox = roi.get("bbox") or [0, 0, 0, 0]
            if bbox[1] > 550:
                continue
            candidates.append(roi)

        if not candidates:
            return None
        return min(candidates, key=lambda roi: ((roi.get("bbox") or [0, 0, 0, 0])[1], (roi.get("bbox") or [0, 0, 0, 0])[0]))

    def extract_payment_priority_from_queue(self, queue_roi):
        direct_value = self.extract_value_after_label_from_row(queue_roi, r'Очередь:?\s*', r'(\d{1,2})')
        if direct_value:
            return direct_value

        qx1, qy1, qx2, qy2 = queue_roi["bbox"]
        qcx = (qx1 + qx2) / 2
        candidates = []

        for roi in self.form_rois:
            if roi["id"] == queue_roi["id"]:
                continue

            txt = roi_text(roi)
            if not txt:
                continue

            rx1, ry1, rx2, ry2 = roi["bbox"]
            gap = ry1 - qy2
            if gap < -5 or gap > 120:
                continue

            x_overlap = max(0, min(qx2, rx2) - max(qx1, rx1))
            covers_center = rx1 <= qcx <= rx2
            if x_overlap <= 0 and not covers_center:
                continue

            matches = re.findall(r'(\d{1,2})', txt)
            if not matches:
                continue

            value = matches[-1]
            score = (max(0, gap), 0 if covers_center else 1, -x_overlap, abs(rx1 - qx1))
            candidates.append((score, value))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        return clean_text(candidates[0][1])

    def extract_bic_after_label(self, text):
        txt = strip_po_markup(text)
        if not txt:
            return None

        m = re.search(r'Код\s+банка:?\s*([A-Za-zА-Яа-я0-9 ]{8,})', txt, flags=re.I)
        candidate = m.group(1) if m else txt
        candidate = normalize_po_bic_candidate(candidate)
        if not candidate:
            return None

        m = re.search(r'([A-Z]{6}[A-Z0-9]{2})', candidate)
        return m.group(1) if m else None

    def extract_bic_from_row(self, base_roi):
        texts = [roi_text(base_roi)]
        seen = {base_roi["id"]}
        current = base_roi

        for _ in range(4):
            right_roi = self.find_right_neighbor(current, max_gap=700)
            if not right_roi or right_roi["id"] in seen:
                break
            seen.add(right_roi["id"])
            texts.append(roi_text(right_roi))
            current = right_roi

        for text in texts:
            code = self.extract_bic_after_label(text)
            if code:
                return code

        return self.extract_bic_after_label(clean_text(" ".join(t for t in texts if t)))

    def find_matching_label_roi(self, anchor_roi, pattern, *, max_gap=120):
        if not anchor_roi:
            return None

        ax1, ay1, ax2, ay2 = anchor_roi["bbox"]
        candidates = []

        for roi in self.find_all_rois(pattern):
            if roi["id"] == anchor_roi["id"]:
                continue

            rx1, ry1, rx2, ry2 = roi["bbox"]
            y_overlap = y_overlap_len(anchor_roi["bbox"], roi["bbox"])
            y_gap = ry1 - ay2

            if y_overlap > 0:
                band = 0
            elif 0 <= y_gap <= max_gap:
                band = 1
            else:
                continue

            score = (band, max(0, y_gap), abs(rx1 - ax1), abs((rx2 - rx1) - (ax2 - ax1)))
            candidates.append((score, roi))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def extract_bic_from_label_roi(self, label_roi):
        if not label_roi:
            return None

        direct_value = self.extract_value_after_label_from_row(
            label_roi,
            r"\u041a\u043e\u0434\s+\u0431\u0430\u043d\u043a\u0430:?\s*",
            r"([A-Za-z\u0410-\u042f\u0430-\u044f0-9 ]{8,})",
        )
        if direct_value:
            code = self.extract_bic_after_label(direct_value)
            if code:
                return code

        row_text = self.collect_same_row_text(label_roi)
        if row_text:
            code = self.extract_bic_after_label(row_text)
            if code:
                return code

        current = label_roi
        seen = {label_roi["id"]}
        for _ in range(3):
            right_roi = self.find_right_neighbor(current, max_gap=800)
            if not right_roi or right_roi["id"] in seen:
                break
            seen.add(right_roi["id"])
            txt = roi_text(right_roi)
            code = self.extract_bic_after_label(txt)
            if code:
                return code
            current = right_roi

        return None

    def extract_section_bank_code(self, section_text):
        cleaned = clean_text(section_text)
        if not cleaned:
            return None
        code = self.extract_bic_after_label(cleaned)
        if code:
            return code
        bics = extract_all_bics(cleaned)
        return bics[0] if bics else None

    def load_raw_ocr_items(self):
        candidates = [
            self.roi_path.with_name(self.roi_path.name.replace("_roi_text.json", "__ocr_raw.json")),
            self.roi_path.with_name(self.roi_path.name.replace("_roi_text.json", "_ocr_raw.json")),
        ]
        for candidate in candidates:
            if candidate.exists():
                data = load_json(candidate)
                return data.get("ocr_items", []) if isinstance(data, dict) else []
        return []

    def extract_executing_bank_from_stamp(self):
        if not self.form_rois:
            return None
        max_y = max((roi.get('bbox') or [0, 0, 0, 0])[3] for roi in self.form_rois)
        candidates = []
        for roi in self.form_rois:
            text = roi_text(roi)
            bbox = roi.get('bbox') or [0, 0, 0, 0]
            if not text or bbox[1] < max_y * 0.65:
                continue
            if not re.search(r'банк', text, flags=re.I):
                continue

            company = None
            names = extract_company_names(text)
            if names:
                company = clean_text(names[0])
            else:
                m = re.search(r'((?:ЗАО|ОАО|ООО)\s*["«\'][^"»\']+["»\'])', text, flags=re.I)
                if m:
                    company = clean_text(m.group(1))

            if company and re.search(r'банк', company, flags=re.I):
                candidates.append((bbox[1], -bbox[0], company))
        if candidates:
            candidates.sort()
            return candidates[0][2]
        return None

    def extract_signatory_from_block(self):
        stop_patterns = (
            r'\bПодпись\s+исполнителя\s+банка\b',
            r'\bДата\s+поступления\b',
            r'\bШтамп\s+банка\b',
        )

        sign_roi = self.find_roi(r'Подписи\s+плательщика:')
        if sign_roi:
            text = roi_text(sign_roi)
            text = re.sub(r'^.*?Подписи\s+плательщика:\s*', '', text or '', flags=re.I)
            text = cleanup_po_field(text, stop_patterns)
            text = re.sub(r'\b[A-Za-z0-9+/=]{8,}\b', ' ', text or '')
            person = extract_person_name(text)
            if person and 'Код' not in person:
                return person

        if not self.form_rois:
            return None
        max_y = max((roi.get('bbox') or [0, 0, 0, 0])[3] for roi in self.form_rois)
        left_texts = []
        for roi in sorted(self.form_rois, key=lambda r: ((r.get('bbox') or [0,0,0,0])[1], (r.get('bbox') or [0,0,0,0])[0])):
            bbox = roi.get('bbox') or [0, 0, 0, 0]
            text = roi_text(roi)
            if not text:
                continue
            if bbox[1] < max_y * 0.70 or bbox[0] > 900:
                continue
            if re.search(r'Подпись\s+исполнителя\s+банка|Дата\s+поступления|Штамп\s+банка', text, flags=re.I):
                continue
            left_texts.append(text)
        if left_texts:
            blob = cleanup_po_field(' '.join(left_texts), stop_patterns)
            blob = re.sub(r'\b[A-Za-z0-9+/=]{8,}\b', ' ', blob or '')
            person = extract_person_name(blob)
            if person and 'Код' not in person:
                return person
        return None

    def extract_ordered_bank_code_values(self):
        label_rois = self.find_all_rois(r"\u041a\u043e\u0434\s+\u0431\u0430\u043d\u043a\u0430:")
        label_rois = sorted(
            label_rois,
            key=lambda roi: (((roi["bbox"][1] + roi["bbox"][3]) / 2), roi["bbox"][0])
        )

        values = []
        for roi in label_rois:
            code = self.extract_bic_from_label_roi(roi)
            if code:
                values.append(code)

        return values
