"""
MANGLAM TRADELINK - GST Tax Invoice PDF Generator
===================================================
Compatible with fpdf 1.7.2 (PyFPDF).
Run directly: produces sample_invoice.pdf with dummy data.
Import generate_invoice(data) from app_cloud.py to get PDF bytes.

Requirements:  pip install fpdf
"""

from fpdf import FPDF
import os

# --- COMPANY CONSTANTS ---
COMPANY_NAME       = "MANGLAM TRADELINK"
COMPANY_ADDR       = "6147/2, Gali Gurudwara, Nabi Karim, Delhi 110055, India"
COMPANY_GSTIN      = "07AEFPG3543M1ZF"
COMPANY_STATE      = "Delhi"
COMPANY_STATE_CODE = "07"
COMPANY_CONTACT    = "9311505051, 9899933500"
COMPANY_EMAIL      = "kansalvikrant01@gmail.com"
COMPANY_UDYAM      = "UDYAM-DL-01-0037125-Micro"
COMPANY_PAN        = "AEFPG3543M"
BANK_NAME          = "Kotak Mahindra Bank Ltd."
BANK_ACNO          = "01722000025625"
BANK_BRANCH_IFSC   = "KG Marg, New Delhi & KKBK0000172"


# --- AMOUNT TO WORDS (Indian format) ---
def _num_to_words(n):
    if n == 0:
        return "Zero"
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
            "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
            "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
            "Sixty", "Seventy", "Eighty", "Ninety"]

    def _below_hundred(x):
        if x < 20:
            return ones[x]
        return (tens[x // 10] + " " + ones[x % 10]).strip()

    def _below_thousand(x):
        if x < 100:
            return _below_hundred(x)
        return ones[x // 100] + " Hundred" + (" and " + _below_hundred(x % 100) if x % 100 else "")

    parts = []
    if n >= 10000000:
        parts.append(_below_hundred(n // 10000000) + " Crore")
        n %= 10000000
    if n >= 100000:
        parts.append(_below_hundred(n // 100000) + " Lakh")
        n %= 100000
    if n >= 1000:
        parts.append(_below_hundred(n // 1000) + " Thousand")
        n %= 1000
    if n > 0:
        parts.append(_below_thousand(n))
    return " ".join(parts)


def amount_in_words(amount):
    rupees = int(amount)
    paise  = round((amount - rupees) * 100)
    text = "INR " + _num_to_words(rupees)
    if paise:
        text += " and " + _num_to_words(paise) + " Paise"
    text += " Only"
    return text


def _s(text):
    """Sanitize for FPDF built-in fonts (latin-1 safe)."""
    return str(text).encode('latin-1', 'replace').decode('latin-1')


# --- INVOICE PDF BUILDER ---
def generate_invoice(data):
    """
    Generate invoice PDF and return raw PDF bytes.

    Expected `data` keys:
        buyer_name, buyer_address, buyer_gstin, buyer_pan,
        buyer_state, buyer_state_code, place_of_supply, buyer_contact,
        invoice_no, invoice_date, payment_terms, other_ref,
        despatched_through, destination, eway_bill_no, vehicle_no,
        items: list of dicts {name, hsn, qty, rate, unit, per, gst_pct, gst_type}
        subtotal, cgst, sgst, igst, cgst_pct, sgst_pct, igst_pct,
        round_off, grand_total
    """
    pdf = FPDF('P', 'mm', 'A4')
    pdf.set_auto_page_break(False, 10)
    pdf.set_margins(8, 8, 8)
    pdf.add_page()

    M  = 8       # margin
    CW = 194     # content width (210 - 2*8)

    # ================================================================
    # SECTION 1: HEADER
    # ================================================================
    y = M
    header_h = 28
    pdf.rect(M, y, CW, header_h)

    # Tax Invoice label
    pdf.set_xy(M, y + 1)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(CW, 4, _s("TAX INVOICE"), 0, 0, "C")

    # Company Name
    pdf.set_xy(M, y + 5)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(CW, 6, _s(COMPANY_NAME), 0, 0, "C")

    # Address
    pdf.set_xy(M, y + 11)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(CW, 4, _s(COMPANY_ADDR), 0, 0, "C")

    # GSTIN line
    pdf.set_xy(M, y + 15)
    pdf.cell(CW, 4, _s("GSTIN/UIN: %s | State Name: %s, Code: %s" % (COMPANY_GSTIN, COMPANY_STATE, COMPANY_STATE_CODE)), 0, 0, "C")

    # Contact line
    pdf.set_xy(M, y + 19)
    pdf.cell(CW, 4, _s("Contact: %s | E-Mail: %s" % (COMPANY_CONTACT, COMPANY_EMAIL)), 0, 0, "C")

    # UDYAM
    pdf.set_xy(M, y + 23)
    pdf.cell(CW, 4, _s(COMPANY_UDYAM), 0, 0, "C")

    # ================================================================
    # SECTION 2: BUYER + INVOICE DETAILS (Two columns)
    # ================================================================
    y_start = M + header_h
    half = CW / 2.0
    box_h = 57
    lh = 4.5
    fs = 7

    pdf.rect(M, y_start, CW, box_h)
    pdf.line(M + half, y_start, M + half, y_start + box_h)

    # --- LEFT: Buyer Details ---
    x = M + 1
    y = y_start + 1
    pdf.set_font("Helvetica", "", fs)

    def buyer_line(label, value, bold_val=False):
        nonlocal y
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "", fs)
        pdf.cell(28, lh, _s(label), 0, 0, "L")
        pdf.set_font("Helvetica", "B" if bold_val else "", fs)
        pdf.cell(half - 30, lh, _s(value), 0, 0, "L")
        pdf.set_font("Helvetica", "", fs)
        y += lh

    buyer_line("Buyer:", data.get("buyer_name", ""), bold_val=True)
    addr = data.get("buyer_address", "")
    for i, aline in enumerate(addr.split("\n")[:3]):
        buyer_line("Address:" if i == 0 else "", aline)
    buyer_line("GSTIN/UIN:", data.get("buyer_gstin", ""))
    buyer_line("PAN/IT No:", data.get("buyer_pan", ""))
    buyer_line("State Name:", "%s, Code: %s" % (data.get("buyer_state", "Delhi"), data.get("buyer_state_code", "07")))
    buyer_line("Place of Supply:", data.get("place_of_supply", "Delhi"))
    buyer_line("Contact:", data.get("buyer_contact", ""))

    # --- Ship To Details (if different from Billing) ---
    ship_to_name = data.get("ship_to_name", "").strip()
    if ship_to_name:
        y += 1
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "B", fs)
        pdf.cell(half - 2, lh, _s("Ship To:"), 0, 0, "L")
        pdf.set_font("Helvetica", "", fs)
        y += lh
        buyer_line("Name:", ship_to_name, bold_val=True)
        ship_addr = data.get("ship_to_address", "")
        for si, sline in enumerate(ship_addr.split("\n")[:3]):
            buyer_line("Address:" if si == 0 else "", sline)
        ship_gstin = data.get("ship_to_gstin", "")
        if ship_gstin:
            buyer_line("GSTIN:", ship_gstin)

    # Expand buyer box if Ship To pushed content further
    actual_buyer_h = y - y_start + 1
    if actual_buyer_h > box_h:
        box_h = actual_buyer_h

    # --- RIGHT: Invoice Details ---
    x2 = M + half + 1
    y = y_start + 1

    def inv_line(label, value):
        nonlocal y
        pdf.set_xy(x2, y)
        pdf.set_font("Helvetica", "", fs)
        pdf.cell(30, lh, _s(label), 0, 0, "L")
        pdf.set_font("Helvetica", "B", fs)
        pdf.cell(half - 32, lh, _s(value), 0, 0, "L")
        pdf.set_font("Helvetica", "", fs)
        y += lh

    inv_line("Invoice No.:", data.get("invoice_no", ""))
    inv_line("Dated:", data.get("invoice_date", ""))
    inv_line("Mode/Terms:", data.get("payment_terms", ""))
    inv_line("Other Ref.:", data.get("other_ref", ""))
    inv_line("Despatched via:", data.get("despatched_through", ""))
    inv_line("Destination:", data.get("destination", ""))
    eway = data.get("eway_bill_no", "").strip()
    vehicle = data.get("vehicle_no", "").strip()
    if eway:
        inv_line("e-Way Bill No.:", eway)
    if vehicle:
        inv_line("Vehicle No.:", vehicle)

    # ================================================================
    # SECTION 3: ITEMS TABLE
    # ================================================================
    y_top = y_start + box_h
    items = data.get("items", [])
    rh = 5
    cols = [10, 68, 20, 20, 22, 14, 40]

    # Header row
    pdf.set_font("Helvetica", "B", fs)
    headers = ["SI No.", "Description of Goods", "HSN/SAC", "Quantity", "Rate", "per", "Amount"]
    hdr_h = 8
    pdf.rect(M, y_top, CW, hdr_h)
    cx = M
    for i, hdr in enumerate(headers):
        pdf.set_xy(cx, y_top)
        pdf.cell(cols[i], hdr_h, _s(hdr), 0, 0, "C")
        if i < len(headers) - 1:
            pdf.line(cx + cols[i], y_top, cx + cols[i], y_top + hdr_h)
        cx += cols[i]

    y = y_top + hdr_h

    # Item rows
    pdf.set_font("Helvetica", "", fs)
    for idx, item in enumerate(items, 1):
        taxable = item["qty"] * item["rate"]
        vals = [
            str(idx),
            item["name"],
            item.get("hsn", ""),
            "%.2f %s" % (item["qty"], item.get("unit", "SQM")),
            "%.2f" % item["rate"],
            item.get("per", "SQM"),
            "{:,.2f}".format(taxable)
        ]
        cx = M
        for i, v in enumerate(vals):
            pdf.set_xy(cx, y)
            al = "R" if i in (3, 4, 6) else ("C" if i == 0 else "L")
            pdf.cell(cols[i], rh, _s(v), 0, 0, al)
            if i < len(vals) - 1:
                pdf.line(cx + cols[i], y, cx + cols[i], y + rh)
            cx += cols[i]
        y += rh

    # Empty space to push totals down
    min_bottom = y_top + hdr_h + max(len(items) * rh, 60)
    items_end_y = y  # where actual items end
    if y < min_bottom:
        y = min_bottom

    # Draw column separators through empty space
    cx = M
    for i in range(len(cols) - 1):
        cx += cols[i]
        pdf.line(cx, items_end_y, cx, y)

    # Tax sub-rows
    cgst_amt   = data.get("cgst", 0.0)
    sgst_amt   = data.get("sgst", 0.0)
    igst_amt   = data.get("igst", 0.0)
    round_off  = data.get("round_off", 0.0)
    grand_total = data.get("grand_total", 0.0)

    tax_lines = []
    if cgst_amt:
        tax_lines.append(("CGST @ %s%%" % data.get("cgst_pct", ""), "{:,.2f}".format(cgst_amt)))
    if sgst_amt:
        tax_lines.append(("SGST @ %s%%" % data.get("sgst_pct", ""), "{:,.2f}".format(sgst_amt)))
    if igst_amt:
        tax_lines.append(("IGST @ %s%%" % data.get("igst_pct", ""), "{:,.2f}".format(igst_amt)))
    if round_off:
        tax_lines.append(("Round Off", "{:,.2f}".format(round_off)))
    tax_lines.append(("Total", "{:,.2f}".format(grand_total)))

    label_w = sum(cols[:6])
    amt_w = cols[6]

    for label, val in tax_lines:
        pdf.line(M, y, M + CW, y)
        pdf.set_xy(M, y)
        pdf.set_font("Helvetica", "B" if label == "Total" else "", fs)
        pdf.cell(label_w, rh, _s(label), 0, 0, "R")
        pdf.line(M + label_w, y, M + label_w, y + rh)
        pdf.cell(amt_w, rh, _s(val), 0, 0, "R")
        pdf.set_font("Helvetica", "", fs)
        y += rh

    # Close items table box
    pdf.rect(M, y_top, CW, y - y_top)

    # Amount in Words
    y += 1
    pdf.set_xy(M, y)
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(CW, 4, _s("Amount Chargeable (in words): %s" % amount_in_words(grand_total)), 0, 0, "L")
    y += 5

    # ================================================================
    # SECTION 4: TAX BREAKDOWN TABLE
    # ================================================================
    y_tax = y
    tcols = [25, 35, 18, 24, 18, 24, 25]
    diff = CW - sum(tcols)
    tcols[1] += diff

    h1 = 5
    h2 = 5
    pdf.rect(M, y_tax, CW, h1 + h2)

    # Top header row
    pdf.set_font("Helvetica", "B", 6.5)
    hx = M
    # HSN/SAC
    pdf.set_xy(hx, y_tax)
    pdf.cell(tcols[0], h1, _s("HSN/SAC"), 0, 0, "C")
    pdf.line(hx + tcols[0], y_tax, hx + tcols[0], y_tax + h1)
    hx += tcols[0]
    # Taxable Value
    pdf.set_xy(hx, y_tax)
    pdf.cell(tcols[1], h1, _s("Taxable Value"), 0, 0, "C")
    pdf.line(hx + tcols[1], y_tax, hx + tcols[1], y_tax + h1)
    hx += tcols[1]
    # Central Tax (spans 2 cols)
    span_c = tcols[2] + tcols[3]
    pdf.set_xy(hx, y_tax)
    pdf.cell(span_c, h1, _s("Central Tax"), 0, 0, "C")
    pdf.line(hx + span_c, y_tax, hx + span_c, y_tax + h1)
    hx += span_c
    # State Tax (spans 2 cols)
    span_s = tcols[4] + tcols[5]
    pdf.set_xy(hx, y_tax)
    pdf.cell(span_s, h1, _s("State Tax"), 0, 0, "C")
    pdf.line(hx + span_s, y_tax, hx + span_s, y_tax + h1)
    hx += span_s
    # Total Tax Amount
    pdf.set_xy(hx, y_tax)
    pdf.cell(tcols[6], h1, _s("Total Tax"), 0, 0, "C")

    # Sub header row
    pdf.line(M, y_tax + h1, M + CW, y_tax + h1)
    sub_heads = ["", "", "Rate", "Amount", "Rate", "Amount", ""]
    pdf.set_font("Helvetica", "", 6.5)
    hx = M
    for i, sh in enumerate(sub_heads):
        pdf.set_xy(hx, y_tax + h1)
        pdf.cell(tcols[i], h2, _s(sh), 0, 0, "C")
        if i < len(sub_heads) - 1:
            pdf.line(hx + tcols[i], y_tax + h1, hx + tcols[i], y_tax + h1 + h2)
        hx += tcols[i]

    y = y_tax + h1 + h2

    # Tax data rows grouped by HSN
    hsn_map = {}
    for item in items:
        hsn = item.get("hsn", "N/A")
        taxable = item["qty"] * item["rate"]
        gst_pct = item.get("gst_pct", 18)
        gst_type = item.get("gst_type", "Local")
        key = (hsn, gst_pct, gst_type)
        hsn_map[key] = hsn_map.get(key, 0.0) + taxable

    total_taxable = 0.0
    total_ctax = 0.0
    total_stax = 0.0
    total_tax_all = 0.0

    pdf.set_font("Helvetica", "", 6.5)
    for (hsn, gst_pct, gst_type), taxable in hsn_map.items():
        total_taxable += taxable
        if "Local" in str(gst_type):
            half_rate = gst_pct / 2.0
            c_amt = taxable * half_rate / 100
            s_amt = taxable * half_rate / 100
            c_rate_str = "%.1f%%" % half_rate
            s_rate_str = "%.1f%%" % half_rate
        else:
            c_amt = 0
            s_amt = 0
            c_rate_str = "-"
            s_rate_str = "-"

        total_ctax += c_amt
        total_stax += s_amt
        line_tax = c_amt + s_amt
        if "Interstate" in str(gst_type):
            line_tax = taxable * gst_pct / 100
        total_tax_all += line_tax

        vals = [hsn, "{:,.2f}".format(taxable), c_rate_str, "{:,.2f}".format(c_amt),
                s_rate_str, "{:,.2f}".format(s_amt), "{:,.2f}".format(line_tax)]
        pdf.line(M, y, M + CW, y)
        hx = M
        for i, v in enumerate(vals):
            pdf.set_xy(hx, y)
            pdf.cell(tcols[i], rh, _s(v), 0, 0, "R" if i > 0 else "C")
            if i < len(vals) - 1:
                pdf.line(hx + tcols[i], y, hx + tcols[i], y + rh)
            hx += tcols[i]
        y += rh

    # Totals row
    pdf.line(M, y, M + CW, y)
    pdf.set_font("Helvetica", "B", 6.5)
    tot_vals = ["Total", "{:,.2f}".format(total_taxable), "", "{:,.2f}".format(total_ctax),
                "", "{:,.2f}".format(total_stax), "{:,.2f}".format(total_tax_all)]
    hx = M
    for i, v in enumerate(tot_vals):
        pdf.set_xy(hx, y)
        pdf.cell(tcols[i], rh, _s(v), 0, 0, "R" if i > 0 else "C")
        if i < len(tot_vals) - 1:
            pdf.line(hx + tcols[i], y, hx + tcols[i], y + rh)
        hx += tcols[i]
    y += rh

    # Close tax table
    pdf.rect(M, y_tax, CW, y - y_tax)

    # Tax Amount in Words
    y += 1
    pdf.set_xy(M, y)
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(CW, 4, _s("Tax Amount (in words): %s" % amount_in_words(total_tax_all)), 0, 0, "L")
    y += 5

    # ================================================================
    # SECTION 5: FOOTER (PAN, Declaration, Bank, Signatures)
    # ================================================================
    # Company PAN
    pdf.set_xy(M, y)
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(CW, 4, _s("Company's PAN: %s" % COMPANY_PAN), 0, 0, "L")
    y += 5

    # Declaration + Bank box
    box_h = 28
    pdf.rect(M, y, CW, box_h)
    pdf.line(M + half, y, M + half, y + box_h)

    # LEFT - Declaration
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_xy(M + 1, y + 1)
    pdf.cell(half - 2, 3.5, _s("Declaration:"), 0, 0, "L")

    pdf.set_font("Helvetica", "", 5.5)
    pdf.set_xy(M + 1, y + 5)
    pdf.multi_cell(half - 3, 3,
        _s("We declare that this invoice shows the actual price of the goods "
           "described and that all particulars are true and correct.\n\n"
           "Goods once sold will not be taken back. Interest @18% p.a. will be "
           "charged if payment is not made within the stipulated time."))

    # RIGHT - Bank Details
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_xy(M + half + 1, y + 1)
    pdf.cell(half - 2, 3.5, _s("Company's Bank Details:"), 0, 0, "L")

    bx = M + half + 1
    by = y + 5
    blh = 3.8
    for label, val in [("Bank Name:", BANK_NAME), ("A/c No.:", BANK_ACNO), ("Branch & IFS Code:", BANK_BRANCH_IFSC)]:
        pdf.set_xy(bx, by)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.cell(28, blh, _s(label), 0, 0, "L")
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.cell(half - 30, blh, _s(val), 0, 0, "L")
        by += blh

    y_sig = y + box_h

    # Signatures
    sig_h = 18
    pdf.rect(M, y_sig, CW, sig_h)
    pdf.line(M + half, y_sig, M + half, y_sig + sig_h)

    pdf.set_font("Helvetica", "", 7)
    pdf.set_xy(M + 2, y_sig + sig_h - 5)
    pdf.cell(half - 4, 4, _s("Customer's Seal and Signature"), 0, 0, "C")

    pdf.set_font("Helvetica", "B", 7)
    pdf.set_xy(M + half + 2, y_sig + 1)
    pdf.cell(half - 4, 4, _s("for %s" % COMPANY_NAME), 0, 0, "R")

    pdf.set_font("Helvetica", "", 7)
    pdf.set_xy(M + half + 2, y_sig + sig_h - 5)
    pdf.cell(half - 4, 4, _s("Authorised Signatory"), 0, 0, "R")

    # Computer generated notice
    pdf.set_font("Helvetica", "", 6)
    pdf.set_xy(M, y_sig + sig_h + 1)
    pdf.cell(CW, 3, _s("This is a Computer Generated Invoice"), 0, 0, "C")

    # --- OUTPUT ---
    # fpdf 1.7.2: output('S') returns the PDF as a string (bytes in Python 3)
    return pdf.output(dest='S').encode('latin-1') if isinstance(pdf.output(dest='S'), str) else pdf.output(dest='S')


# --- MAIN: GENERATE SAMPLE ---
if __name__ == "__main__":
    sample_data = {
        "buyer_name": "M/S SHARMA TEXTILES PVT LTD",
        "buyer_address": "45, Industrial Area Phase-II\nGurgaon, Haryana 122015",
        "buyer_gstin": "06AABCS1234F1Z5",
        "buyer_pan": "AABCS1234F",
        "buyer_state": "Delhi",
        "buyer_state_code": "07",
        "place_of_supply": "Delhi",
        "buyer_contact": "9876543210",

        "invoice_no": "GST/25-26/0434",
        "invoice_date": "13-Mar-2026",
        "payment_terms": "Credit 30 Days",
        "other_ref": "",
        "despatched_through": "VRL Logistics",
        "destination": "Gurgaon",
        "eway_bill_no": "1234 5678 9012",
        "vehicle_no": "DL 01 AB 1234",

        "items": [
            {"name": "PVC COATED FABRIC SQM",  "hsn": "5903", "qty": 735,  "rate": 25.50, "unit": "SQM", "per": "SQM", "gst_pct": 18, "gst_type": "Local (CGST + SGST)"},
            {"name": "REXINE ROLL 54 INCH",     "hsn": "5903", "qty": 120,  "rate": 42.00, "unit": "MTR", "per": "MTR", "gst_pct": 18, "gst_type": "Local (CGST + SGST)"},
            {"name": "FOAM SHEET 40D 1 INCH",   "hsn": "3921", "qty": 50,   "rate": 85.00, "unit": "PCS", "per": "PCS", "gst_pct": 18, "gst_type": "Local (CGST + SGST)"},
        ],

        "subtotal": 735*25.50 + 120*42.00 + 50*85.00,
        "cgst": (735*25.50 + 120*42.00 + 50*85.00) * 9 / 100,
        "sgst": (735*25.50 + 120*42.00 + 50*85.00) * 9 / 100,
        "igst": 0.0,
        "cgst_pct": "9",
        "sgst_pct": "9",
        "igst_pct": "",
        "round_off": 0.0,
        "grand_total": 0.0,
    }

    exact = sample_data["subtotal"] + sample_data["cgst"] + sample_data["sgst"] + sample_data["igst"]
    sample_data["grand_total"] = round(exact)
    sample_data["round_off"] = round(sample_data["grand_total"] - exact, 2)

    pdf_bytes = generate_invoice(sample_data)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_invoice.pdf")
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)

    print("Invoice generated: %s" % out_path)
    print("   Subtotal:    Rs. {:,.2f}".format(sample_data["subtotal"]))
    print("   CGST @9%%:   Rs. {:,.2f}".format(sample_data["cgst"]))
    print("   SGST @9%%:   Rs. {:,.2f}".format(sample_data["sgst"]))
    print("   Grand Total: Rs. {:,.2f}".format(sample_data["grand_total"]))
