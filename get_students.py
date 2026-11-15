import os
import re
import time
import json
import traceback
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import Select

# ==============================================================================
# MASTER CODE LOOKUP TABLES (UDISE+ SDMS Standard Codes)
# ==============================================================================
BLOOD_GROUP_MAP = {
    "1": "A+", "01": "A+", "1 - A+": "A+", "A+": "A+",
    "2": "A-", "02": "A-", "2 - A-": "A-", "A-": "A-",
    "3": "B+", "03": "B+", "3 - B+": "B+", "B+": "B+",
    "4": "B-", "04": "B-", "4 - B-": "B-", "B-": "B-",
    "5": "O+", "05": "O+", "5 - O+": "O+", "O+": "O+",
    "6": "O-", "06": "O-", "6 - O-": "O-", "O-": "O-",
    "7": "AB+", "07": "AB+", "7 - AB+": "AB+", "AB+": "AB+",
    "8": "AB-", "08": "AB-", "8 - AB-": "AB-", "AB-": "AB-",
    "9": ""
}

SOCIAL_CAT_MAP = {
    "1": "GENERAL", "01": "GENERAL", "1 - GENERAL": "GENERAL", "1-GENERAL": "GENERAL",
    "2": "SC", "02": "SC", "2 - SC": "SC", "2-SC": "SC",
    "3": "ST", "03": "ST", "3 - ST": "ST", "3-ST": "ST",
    "4": "OBC", "04": "OBC", "4 - OBC": "OBC", "4-OBC": "OBC"
}

MINORITY_MAP = {
    "1": "Muslim", "2": "Christian", "3": "Sikh",
    "4": "Buddhist", "5": "Parsi", "6": "Jain",
    "7": "NA", "7 - NA": "NA", "7-NA": "NA"
}

YES_NO_MAP = {
    "1": "Yes", "true": "Yes", "yes": "Yes", "y": "Yes",
    "2": "No", "0": "No", "false": "No", "no": "No", "n": "No"
}

UDISE_CLASS_ID_MAP = {
    "93": "NURSERY", "94": "LKG", "95": "UKG",
    "13": "NURSERY", "14": "LKG", "15": "UKG",
    "-3": "NURSERY", "-2": "LKG", "-1": "UKG", "0": "UKG",
    "1": "I", "2": "II", "3": "III", "4": "IV",
    "5": "V", "6": "VI", "7": "VII", "8": "VIII",
    "9": "IX", "10": "X", "11": "XI", "12": "XII"
}

ODIA_DIGITS = str.maketrans("0123456789", "୦୧୨୩୪୫୬୭୮୯")

ODIA_CLASS_MAP = {
    "NURSERY": "ଶିଶୁ ବାଟିକା", "LKG": "ଶିଶୁ ବାଟିକା", "UKG": "ଶିଶୁ ବାଟିକା", "SHISHUVATIKA": "ଶିଶୁ ବାଟିକା",
    "I": "ପ୍ରଥମ", "1": "ପ୍ରଥମ",
    "II": "ଦ୍ଵିତୀୟ", "2": "ଦ୍ଵିତୀୟ",
    "III": "ତୃତୀୟ", "3": "ତୃତୀୟ",
    "IV": "ଚତୁର୍ଥ", "4": "ଚତୁର୍ଥ",
    "V": "ପଞ୍ଚମ", "5": "ପଞ୍ଚମ",
    "VI": "ଷଷ୍ଠ", "6": "ଷଷ୍ଠ",
    "VII": "ସପ୍ତମ", "7": "ସପ୍ତମ",
    "VIII": "ଅଷ୍ଟମ", "8": "ଅଷ୍ଟମ",
    "IX": "ନବମ", "9": "ନବମ",
    "X": "ଦଶମ", "10": "ଦଶମ",
    "XI": "ଏକାଦଶ", "11": "ଏକାଦଶ",
    "XII": "ଦ୍ଵାଦଶ", "12": "ଦ୍ଵାଦଶ"
}

def to_odia_digits(val):
    if not val:
        return ""
    return str(val).translate(ODIA_DIGITS)

def build_odia_records(records):
    """
    Creates an Odia-ready copy of all student records:
    - Class -> ପ୍ରଥମ, ଦ୍ଵିତୀୟ... (plus 'Class (With Label)' -> ଶ୍ରେଣୀ - ପ୍ରଥମ)
    - Roll No, Date of Birth, Phone Number, Pincode, PEN, AADHAAR -> Odia digits (୦-୯)
    - Blood Group -> Always kept in English (O+, A+, B+, AB+)
    - Name, Father's Name, Mother's Name, Address -> Kept ready for manual Odia update
    """
    odia_list = []
    for r in records:
        cls_en = str(r.get("Class", "")).strip().upper()
        cls_odia = ODIA_CLASS_MAP.get(cls_en, to_odia_digits(cls_en))
        gender_en = str(r.get("Gender", "")).strip()
        gender_odia = "ବାଳକ" if gender_en == "Male" else ("ବାଳିକା" if gender_en == "Female" else gender_en)

        odia_list.append({
            "Name": r.get("Name", ""),  # Update manually in Odia as needed
            "Class": cls_odia,
            "Class (With Label)": f"ଶ୍ରେଣୀ - {cls_odia}" if cls_odia else "",
            "Section": r.get("Section", ""),
            "Roll No": to_odia_digits(r.get("Roll No", "")),
            "Date of Birth": to_odia_digits(r.get("Date of Birth", "")),
            "Gender": gender_odia,
            "Blood Group": r.get("Blood Group", ""),  # Strictly kept in English!
            "Phone Number": to_odia_digits(r.get("Phone Number", "")),
            "Alternate Phone": to_odia_digits(r.get("Alternate Phone", "")),
            "Father's Name": r.get("Father's Name", ""),  # Update manually in Odia as needed
            "Mother's Name": r.get("Mother's Name", ""),  # Update manually in Odia as needed
            "Guardian's Name": r.get("Guardian's Name", ""),
            "Address": to_odia_digits(r.get("Address", "")),  # Pincode in Odia digits
            "Pincode": to_odia_digits(r.get("Pincode", "")),
            "PEN": to_odia_digits(r.get("PEN", "")),
            "AADHAAR Number": to_odia_digits(r.get("AADHAAR Number", "")),
            "Name as per AADHAAR": r.get("Name as per AADHAAR", ""),
            "APAAR ID": to_odia_digits(r.get("APAAR ID", "")),
            "Admission Number": to_odia_digits(r.get("Admission Number", "")),
            "Admission Date": to_odia_digits(r.get("Admission Date", "")),
            "Social Category": r.get("Social Category", ""),
            "Minority Group": r.get("Minority Group", ""),
            "Mother Tongue": r.get("Mother Tongue", ""),
            "BPL Beneficiary": r.get("BPL Beneficiary", ""),
            "AAY Beneficiary": r.get("AAY Beneficiary", ""),
            "EWS Group": r.get("EWS Group", ""),
            "CWSN": r.get("CWSN", ""),
            "Impairment Type": r.get("Impairment Type", ""),
            "Email ID": r.get("Email ID", ""),
            "Student State Code": to_odia_digits(r.get("Student State Code", "")),
            "Entry Status": r.get("Entry Status", ""),
            "Student ID": r.get("Student ID", "")
        })
    return odia_list

def normalize_class(raw_cls):
    if raw_cls is None:
        return ""
    s = str(raw_cls).strip().upper()
    if not s or s in ("NONE", "NULL"):
        return ""
    if s in UDISE_CLASS_ID_MAP:
        return UDISE_CLASS_ID_MAP[s]
    if "UKG" in s or "KG2" in s or "PP1" in s:
        return "UKG"
    if "LKG" in s or "KG1" in s or "PP2" in s:
        return "LKG"
    if "NUR" in s or "PP3" in s or "BALVATIKA" in s:
        return "NURSERY"
    s_clean = re.sub(r'^(CLASS|CLS|STD|STANDARD|GRADE)[\s\-:.]*', '', s).strip()
    num_to_roman = {
        '1': 'I', '01': 'I', '2': 'II', '02': 'II', '3': 'III', '03': 'III',
        '4': 'IV', '04': 'IV', '5': 'V', '05': 'V', '6': 'VI', '06': 'VI',
        '7': 'VII', '07': 'VII', '8': 'VIII', '08': 'VIII', '9': 'IX', '09': 'IX',
        '10': 'X', '11': 'XI', '12': 'XII'
    }
    return num_to_roman.get(s_clean, s_clean)

def smart_pick(d, exact_keys, substring_keywords=None):
    """Pick first non-empty scalar value from exact_keys, or fallback to key substring match."""
    for k in exact_keys:
        v = d.get(k)
        if v is not None and not isinstance(v, (dict, list)):
            s = str(v).strip()
            if s and s.lower() not in ("none", "null"):
                return s
    if substring_keywords:
        for k, v in d.items():
            if v is None or isinstance(v, (dict, list)):
                continue
            kl = k.lower()
            if any(kw in kl for kw in substring_keywords):
                s = str(v).strip()
                if s and s.lower() not in ("none", "null"):
                    return s
    return ""

def format_yes_no(val):
    if not val:
        return ""
    s = str(val).strip()
    return YES_NO_MAP.get(s.lower(), s)

def format_date(dob):
    if not dob:
        return ""
    s = str(dob).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}', s):
        parts = s[:10].split("-")
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return s

# ==============================================================================
# BROWSER JAVASCRIPT: FETCH ALL STUDENTS + GENERAL PROFILES (GP) IN ONE GO
# ==============================================================================
JS_INSTALL_XHR_SPY = """
if (!window.__udiseSpyInstalled) {
    window.__udiseSpyInstalled = true;
    window.__capturedApiHeaders = {};
    window.__capturedAllStudents = null;

    const origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        this.__reqUrl = url || '';
        return origOpen.apply(this, arguments);
    };

    const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
    XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
        if (name && value) {
            window.__capturedApiHeaders[name] = value;
        }
        return origSetHeader.apply(this, arguments);
    };

    const origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function() {
        this.addEventListener('load', function() {
            try {
                if (this.__reqUrl && this.__reqUrl.includes('/api/cy/students/all/')) {
                    window.__capturedAllStudents = JSON.parse(this.responseText);
                }
            } catch (e) {}
        });
        return origSend.apply(this, arguments);
    };
}
"""

JS_FETCH_ALL_STUDENTS_AND_GP = """
const callback = arguments[arguments.length - 1];
const schoolId = arguments[0];

(async () => {
    try {
        const headers = Object.assign(
            { 'Accept': 'application/json, text/plain, */*' },
            window.__capturedApiHeaders || {}
        );

        if (!headers['Authorization'] && !headers['authorization']) {
            for (const store of [window.sessionStorage, window.localStorage]) {
                for (let i = 0; i < store.length; i++) {
                    const k = store.key(i) || '';
                    const v = store.getItem(k) || '';
                    if (k.toLowerCase().includes('token') || k.toLowerCase().includes('auth') || v.includes('eyJ')) {
                        const clean = v.replace(/^"|"$/g, '');
                        if (clean.startsWith('eyJ')) {
                            headers['Authorization'] = 'Bearer ' + clean;
                            break;
                        }
                    }
                }
                if (headers['Authorization']) break;
            }
        }

        // 1. Fetch all active students for the school
        let allJson = window.__capturedAllStudents;
        if (!allJson) {
            const allUrl = `https://sdms.udiseplus.gov.in/p1/api/cy/students/all/${schoolId}`;
            const allResp = await fetch(allUrl, { method: 'GET', credentials: 'include', headers });
            if (!allResp.ok) {
                return callback({ ok: false, error: 'all_api_status_' + allResp.status });
            }
            allJson = await allResp.json();
        }

        const rawList = Array.isArray(allJson?.data)
            ? allJson.data
            : (Array.isArray(allJson?.data?.students) ? allJson.data.students : (Array.isArray(allJson) ? allJson : []));

        if (!rawList.length) {
            return callback({ ok: false, error: 'empty_all_list' });
        }

        // 2. Fetch General Profile (GP - Form 1) for every student in parallel batches of 8
        //    Endpoint: GET https://sdms.udiseplus.gov.in/p1/api/cy/students/{studentId}
        const enriched = [];
        const batchSize = 8;
        for (let i = 0; i < rawList.length; i += batchSize) {
            const batch = rawList.slice(i, i + batchSize);
            const gpResults = await Promise.all(batch.map(async (st) => {
                const stId = st.studentId || st.id || st.studId;
                if (!stId) return { base: st, gp: null };
                try {
                    const gpResp = await fetch(`https://sdms.udiseplus.gov.in/p1/api/cy/students/${stId}`, {
                        method: 'GET',
                        credentials: 'include',
                        headers
                    });
                    if (gpResp.ok) {
                        const gpJson = await gpResp.json();
                        return { base: st, gp: gpJson?.data || gpJson };
                    }
                } catch (e) {}
                return { base: st, gp: null };
            }));
            enriched.push(...gpResults);
        }

        return callback({ ok: true, count: enriched.length, records: enriched });
    } catch (err) {
        return callback({ ok: false, error: err.message || String(err) });
    }
})();
"""

# ==============================================================================
# PARSE ALL STUDENT FIELDS FROM UDISE+ API + GP JSON
# ==============================================================================
def parse_api_records(enriched_records):
    parsed = []
    for item in enriched_records:
        base = item.get("base") or {}
        gp = item.get("gp") or {}
        merged = {**base, **gp}

        student_id = smart_pick(merged, ["studentId", "studId", "id"])

        name = smart_pick(
            merged,
            ["studentName", "name", "studName", "studentNameAsPerSchool"],
            ["studentname", "studname"]
        ).upper()

        pen = smart_pick(
            merged,
            ["studentCodeNat", "pen", "nationalCode", "studentPen"],
            ["codenat", "pen"]
        )

        state_code = smart_pick(
            merged,
            ["studentCodeState", "stateCode", "stuStateCode"],
            ["codestate"]
        )

        raw_class = smart_pick(
            merged,
            ["className", "classDesc", "gradeName", "classRoman", "classId", "currentClassId"],
            ["classname", "classdesc", "classid"]
        )
        student_class = normalize_class(raw_class)

        section = smart_pick(
            merged,
            ["sectionName", "sectionDesc", "section", "sectionAlias", "sectionId"],
            ["section"]
        ) or "A"

        roll_no = smart_pick(
            merged,
            ["rollNo", "rollNumber", "classRollNo", "stuRollNo"],
            ["rollno"]
        )

        dob = format_date(smart_pick(
            merged,
            ["dob", "dateOfBirth", "birthDate", "stuDob"],
            ["dob", "birth"]
        ))

        gender_raw = smart_pick(merged, ["genderDesc", "gender"], ["gender"]).upper()
        if gender_raw in ("1", "M", "MALE", "1-MALE"):
            gender = "Male"
        elif gender_raw in ("2", "F", "FEMALE", "2-FEMALE"):
            gender = "Female"
        elif gender_raw in ("3", "T", "TRANSGENDER", "3-TRANSGENDER"):
            gender = "Transgender"
        else:
            gender = gender_raw

        father = smart_pick(
            merged,
            ["fatherName", "fathersName", "stuFatherName"],
            ["father"]
        ).upper()

        mother = smart_pick(
            merged,
            ["motherName", "mothersName", "stuMotherName"],
            ["mother"]
        ).upper()

        guardian = smart_pick(
            merged,
            ["guardianName", "stuGuardianName", "guardian"],
            ["guardian"]
        ).upper()

        mobile = smart_pick(
            merged,
            ["mobileNo", "primaryMobileNo", "mobile", "stuMobileNo", "parentMobileNo", "contactNo", "mobileNumber"],
            ["mobileno", "primarymobile", "mobile", "phone"]
        )
        if mobile in ("0", "None", "null"):
            mobile = ""

        alt_mobile = smart_pick(
            merged,
            ["alternateMobileNo", "altMobileNo", "secondaryMobileNo", "alternateMobile", "altMobile"],
            ["altmobile", "alternatemobile", "secondarymobile"]
        )
        if alt_mobile in ("0", "None", "null"):
            alt_mobile = ""

        email = smart_pick(
            merged,
            ["emailId", "email", "stuEmail", "contactEmail", "parentEmail"],
            ["email"]
        )

        address = smart_pick(
            merged,
            ["address", "stuAddress", "studentAddress", "residentialAddress", "addressLine1", "commAddress", "presentAddress"],
            ["address", "addr"]
        ).upper()

        pincode = smart_pick(
            merged,
            ["pinCode", "pincode", "stuPinCode", "postalCode", "pin"],
            ["pincode", "postal"]
        )
        if pincode in ("0", "None", "null"):
            pincode = ""

        full_address = address
        if pincode and pincode not in full_address:
            full_address = f"{full_address} - {pincode}" if full_address else pincode

        raw_bg = smart_pick(
            merged,
            ["bloodGroupDesc", "bloodGroupName", "bloodGroup", "bloodGroupId", "bloodGroupCode", "stuBloodGroup"],
            ["blood"]
        )
        blood_group = BLOOD_GROUP_MAP.get(raw_bg, raw_bg)
        if "UNDER INVESTIGATION" in blood_group.upper() or blood_group in ("None", "null", "0", "9"):
            blood_group = ""

        # Aadhaar Details (4.1.7 & 4.1.8)
        aadhaar_no = smart_pick(
            merged,
            ["uuid", "aadhaarNo", "aadharNo", "stuUuid", "uuidMask", "aadhaarNumber"],
            ["uuid", "aadhaar", "aadhar"]
        )
        name_as_aadhaar = smart_pick(
            merged,
            ["nameAsAadhaar", "aadhaarName", "stuNameAsAadhaar", "nameInAadhaar", "studentNameAsPerAadhaar"],
            ["nameasaadhaar", "aadhaarname", "nameinaadhaar"]
        ).upper()

        # APAAR / ABC ID
        apaar_id = smart_pick(
            merged,
            ["apaarId", "abcId", "apaarNo", "apaarNumber", "apaarStatus"],
            ["apaar", "abcid"]
        )

        # Admission Number & Date
        admission_no = smart_pick(
            merged,
            ["admissionNo", "admissionNumber", "admNo", "schoolAdmissionNo"],
            ["admissionno", "admno"]
        )
        admission_date = format_date(smart_pick(
            merged,
            ["admissionDate", "admDate", "dateOfAdmission"],
            ["admissiondate", "admdate"]
        ))

        # Social Category, Minority, Mother Tongue, BPL, AAY, EWS, CWSN
        raw_soc = smart_pick(
            merged,
            ["socialCategoryDesc", "socCatDesc", "socCatId", "socialCategory"],
            ["soccat", "socialcat"]
        )
        social_cat = SOCIAL_CAT_MAP.get(raw_soc.upper(), raw_soc)

        raw_min = smart_pick(
            merged,
            ["minorityDesc", "minorityId", "minorityGroup"],
            ["minority"]
        )
        minority = MINORITY_MAP.get(raw_min.upper(), raw_min)

        mother_tongue = smart_pick(
            merged,
            ["motherTongueDesc", "motherTongueName", "motherTongue", "motherTongueId"],
            ["mothertongue"]
        )

        bpl = format_yes_no(smart_pick(merged, ["bplYn", "isBpl", "bplBeneficiary"], ["bpl"]))
        aay = format_yes_no(smart_pick(merged, ["aayYn", "isAay", "aayBeneficiary"], ["aay"]))
        ews = format_yes_no(smart_pick(merged, ["ewsYn", "isEws", "ewsGroup"], ["ews"]))
        cwsn = format_yes_no(smart_pick(merged, ["cwsnYn", "isCwsn", "cwsn"], ["cwsn"]))
        impairment = smart_pick(merged, ["impairmentType", "impairmentDesc", "disabilityType"], ["impairment", "disability"])
        entry_status = smart_pick(merged, ["entryStatus", "statusDesc", "profileStatus"], ["entrystatus"])

        parsed.append({
            "Name": name,
            "Class": student_class,
            "Section": section,
            "Roll No": roll_no if roll_no and roll_no not in ("0", "00") else "",
            "Date of Birth": dob,
            "Gender": gender,
            "Blood Group": blood_group,
            "Phone Number": mobile,
            "Alternate Phone": alt_mobile,
            "Father's Name": father,
            "Mother's Name": mother,
            "Guardian's Name": guardian,
            "Address": full_address,
            "Pincode": pincode,
            "PEN": pen,
            "AADHAAR Number": aadhaar_no,
            "Name as per AADHAAR": name_as_aadhaar,
            "APAAR ID": apaar_id,
            "Admission Number": admission_no,
            "Admission Date": admission_date,
            "Social Category": social_cat,
            "Minority Group": minority,
            "Mother Tongue": mother_tongue,
            "BPL Beneficiary": bpl,
            "AAY Beneficiary": aay,
            "EWS Group": ews,
            "CWSN": cwsn,
            "Impairment Type": impairment,
            "Email ID": email,
            "Student State Code": state_code,
            "Entry Status": entry_status,
            "Student ID": student_id
        })
    return parsed

# ==============================================================================
# SCRAPE ACTIVE STUDENTS TABLE + APAAR MODULE (For Enrichment or Fallback)
# ==============================================================================
def scrape_active_students_table(driver, school_id):
    """Scrapes all visible columns from Active Students (#/school/{schoolId}/listAllStudentCy) including Aadhaar/APAAR."""
    records_by_pen = {}
    records_by_name_dob = {}

    if school_id:
        active_url = f"https://sdms.udiseplus.gov.in/g1/#/school/{school_id}/listAllStudentCy"
        if "listAllStudentCy" not in (driver.current_url or ""):
            driver.get(active_url)
            time.sleep(5)

    # Set items per page to maximum if paginator exists
    try:
        driver.execute_script("""
            const sel = document.querySelector('mat-select');
            if (sel) sel.click();
        """)
        time.sleep(1)
        driver.execute_script("""
            const opts = Array.from(document.querySelectorAll('mat-option'));
            if (opts.length) opts[opts.length - 1].click();
        """)
        time.sleep(3)
    except Exception:
        pass

    page_num = 1
    while True:
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            text = row.text.strip()
            if not text or "Please Wait" in text:
                continue

            name_m = re.search(r'Name\s*-\s*(.+)', text)
            gender_m = re.search(r'Gender\s*-\s*(.+)', text)
            dob_m = re.search(r'DOB\s*-\s*(\d{2}/\d{2}/\d{4})', text)
            pen_m = re.search(r'PEN\s*-\s*(\d+)', text)
            cls_m = re.search(r'Class\s*-\s*(.+)', text)
            sec_m = re.search(r'Section\s*-\s*([A-Za-z0-9]+)', text)
            father_m = re.search(r"Father's Name\s*-\s*(.+)", text)
            mother_m = re.search(r"Mother's Name\s*-\s*(.+)", text)
            soc_m = re.search(r'Social Category\s*-\s*(.+)', text)
            min_m = re.search(r'Minority Group\s*-\s*(.+)', text)
            bpl_m = re.search(r'BPL Beneficiary\s*-\s*(.+)', text)
            cwsn_m = re.search(r'CWSN\s*-\s*(.+)', text)
            imp_m = re.search(r'Type of Impairments\s*-\s*(.+)', text)
            aadhaar_m = re.search(r'AADHAAR No\.\s*:\s*([^\n\r]+)', text)
            aadhaar_name_m = re.search(r'Name as per AADHAAR\s*:\s*([^\n\r]+)', text)
            apaar_m = re.search(r'(?:APAAR|ABC)\s*(?:ID|No\.?)\s*[:\-]\s*([^\n\r]+)', text, re.IGNORECASE)

            name = name_m.group(1).strip().upper() if name_m else ""
            if not name:
                continue
            pen = pen_m.group(1).strip() if pen_m else ""
            dob = dob_m.group(1).strip() if dob_m else ""
            cls = normalize_class(cls_m.group(1).strip() if cls_m else "")
            sec = sec_m.group(1).strip() if sec_m else "A"
            father = father_m.group(1).strip().upper() if father_m else ""
            mother = mother_m.group(1).strip().upper() if mother_m else ""
            gender = gender_m.group(1).strip() if gender_m else ""
            soc = SOCIAL_CAT_MAP.get((soc_m.group(1).strip().upper() if soc_m else ""), (soc_m.group(1).strip() if soc_m else ""))
            minority = MINORITY_MAP.get((min_m.group(1).strip().upper() if min_m else ""), (min_m.group(1).strip() if min_m else ""))
            bpl = bpl_m.group(1).strip() if bpl_m else ""
            cwsn = cwsn_m.group(1).strip() if cwsn_m else ""
            imp = imp_m.group(1).strip() if imp_m else ""
            aadhaar_no = aadhaar_m.group(1).strip() if aadhaar_m else ""
            aadhaar_name = aadhaar_name_m.group(1).strip().upper() if aadhaar_name_m else ""
            apaar_id = apaar_m.group(1).strip() if apaar_m else ""

            rec = {
                "Name": name,
                "Class": cls,
                "Section": sec,
                "Roll No": "",
                "Date of Birth": dob,
                "Gender": gender,
                "Blood Group": "",
                "Phone Number": "",
                "Alternate Phone": "",
                "Father's Name": father,
                "Mother's Name": mother,
                "Guardian's Name": "",
                "Address": "",
                "Pincode": "",
                "PEN": pen,
                "AADHAAR Number": aadhaar_no,
                "Name as per AADHAAR": aadhaar_name,
                "APAAR ID": apaar_id,
                "Admission Number": "",
                "Admission Date": "",
                "Social Category": soc,
                "Minority Group": minority,
                "Mother Tongue": "",
                "BPL Beneficiary": bpl,
                "AAY Beneficiary": "",
                "EWS Group": "",
                "CWSN": cwsn,
                "Impairment Type": imp,
                "Email ID": "",
                "Student State Code": "",
                "Entry Status": "Completed",
                "Student ID": ""
            }
            if pen:
                records_by_pen[pen] = rec
            records_by_name_dob[(name, dob)] = rec

        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Next page']")
            if next_btn.get_attribute("disabled") or "disabled" in (next_btn.get_attribute("class") or ""):
                break
            driver.execute_script("arguments[0].click();", next_btn)
            page_num += 1
            time.sleep(3)
        except Exception:
            break

    return records_by_pen, records_by_name_dob

def scrape_apaar_module(driver, records_by_pen, records_by_name_dob):
    """Switches to APAAR Module and enriches Phone Number & APAAR ID across all classes."""
    try:
        print("  -> Checking APAAR Module for Phone Numbers & APAAR IDs...")
        apaar_links = driver.find_elements(By.XPATH, "//*[contains(text(), 'APAAR Module')]")
        if apaar_links:
            driver.execute_script("arguments[0].click();", apaar_links[0])
            time.sleep(4)

        all_selects = driver.find_elements(By.TAG_NAME, "select")
        class_dropdown_idx = -1
        section_dropdown_idx = -1
        class_names = []

        for idx, sel in enumerate(all_selects):
            opts = [o.text.strip() for o in sel.find_elements(By.TAG_NAME, "option")]
            if any("Select Class" in t or "UKG" in t or " I" in t or t == "I" for t in opts):
                class_dropdown_idx = idx
                class_names = [t for t in opts if t and "Select Class" not in t]
            elif any("Select Section" in t or "All" in t for t in opts):
                section_dropdown_idx = idx

        for target_class in class_names:
            current_selects = driver.find_elements(By.TAG_NAME, "select")
            Select(current_selects[class_dropdown_idx]).select_by_visible_text(target_class)
            if section_dropdown_idx != -1:
                try:
                    sec_sel = Select(current_selects[section_dropdown_idx])
                    sec_opts = [o.text.strip() for o in sec_sel.options]
                    if "All" in sec_opts:
                        sec_sel.select_by_visible_text("All")
                except Exception:
                    pass

            go_btns = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-primary') and normalize-space()='Go']")
            if go_btns:
                driver.execute_script("arguments[0].click();", go_btns[0])
                time.sleep(3)

            for row in driver.find_elements(By.XPATH, "//table/tbody/tr"):
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 2:
                    continue
                r_text = row.text
                pen_m = re.search(r'\b(\d{11})\b', r_text)
                mob_m = re.search(r'\b([6-9]\d{9})\b', r_text)
                dob_m = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', r_text)
                apaar_m = re.search(r'\b(\d{12})\b', r_text)
                name = ""
                try:
                    name = cols[0].find_element(By.CLASS_NAME, "anchorClass").text.strip().upper()
                except Exception:
                    pass

                mobile = mob_m.group(1) if mob_m else ""
                dob = dob_m.group(1) if dob_m else ""
                pen = pen_m.group(1) if pen_m else ""
                apaar = apaar_m.group(1) if apaar_m else ""
                cls_norm = normalize_class(target_class)

                target_rec = None
                if pen and pen in records_by_pen:
                    target_rec = records_by_pen[pen]
                elif (name, dob) in records_by_name_dob:
                    target_rec = records_by_name_dob[(name, dob)]

                if target_rec:
                    if mobile and not target_rec.get("Phone Number"):
                        target_rec["Phone Number"] = mobile
                    if apaar and not target_rec.get("APAAR ID"):
                        target_rec["APAAR ID"] = apaar
                    if cls_norm and not target_rec.get("Class"):
                        target_rec["Class"] = cls_norm
                elif name:
                    new_rec = {
                        "Name": name,
                        "Class": cls_norm,
                        "Section": "A",
                        "Roll No": "",
                        "Date of Birth": dob,
                        "Gender": "",
                        "Blood Group": "",
                        "Phone Number": mobile,
                        "Alternate Phone": "",
                        "Father's Name": "",
                        "Mother's Name": "",
                        "Guardian's Name": "",
                        "Address": "",
                        "Pincode": "",
                        "PEN": pen,
                        "AADHAAR Number": "",
                        "Name as per AADHAAR": "",
                        "APAAR ID": apaar,
                        "Admission Number": "",
                        "Admission Date": "",
                        "Social Category": "",
                        "Minority Group": "",
                        "Mother Tongue": "",
                        "BPL Beneficiary": "",
                        "AAY Beneficiary": "",
                        "EWS Group": "",
                        "CWSN": "",
                        "Impairment Type": "",
                        "Email ID": "",
                        "Student State Code": "",
                        "Entry Status": "",
                        "Student ID": ""
                    }
                    if pen:
                        records_by_pen[pen] = new_rec
                    records_by_name_dob[(name, dob)] = new_rec
    except Exception as e:
        print(f"  [!] APAAR enrichment notice: {e}")

# ==============================================================================
# SORT BY CLASS & SECTION (KEEP ROLL NO BLANK IF NOT IN UDISE)
# ==============================================================================
def sort_and_assign_rolls(records):
    class_order = {
        "NURSERY": 1, "LKG": 2, "UKG": 3,
        "I": 4, "II": 5, "III": 6, "IV": 7, "V": 8,
        "VI": 9, "VII": 10, "VIII": 11, "IX": 12, "X": 13, "XI": 14, "XII": 15
    }
    records.sort(key=lambda r: (
        class_order.get(r.get("Class", ""), 99),
        r.get("Section", "A"),
        r.get("Name", "")
    ))

    for r in records:
        if r.get("Roll No") in ("0", "00", None):
            r["Roll No"] = ""
    return records

# ==============================================================================
# MAIN SCRIPT — 100% MANUAL LOGIN -> PRESS ENTER -> FULL EXCEL GENERATED!
# ==============================================================================
def automate_and_scrape():
    print("======================================================================")
    print("   UDISE+ COMPLETE STUDENT EXTRACTOR -> EXCEL (MANUAL UPLOAD)")
    print("   Extracts: Name, Class, Section, Roll No, DOB, Gender, Blood Group,")
    print("   Phone, Alternate Phone, Father, Mother, Guardian, Address, Pincode,")
    print("   PEN, AADHAAR Number, Name as per AADHAAR, APAAR ID, Social Category,")
    print("   Minority, Mother Tongue, BPL, AAY, EWS, CWSN, Email & Admission Info")
    print("======================================================================\n")

    print("Launching Chrome browser...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

    portal_url = "https://udiseplus.gov.in/#/en/page/statelogin"
    driver.get(portal_url)

    print("\n--- INSTRUCTIONS ---")
    print("1. Log in to UDISE+ (enter your UDISE Code, Password, and CAPTCHA).")
    print("2. Click 'Go to UDISE+ Portal (Current Academic Year)' so the Student Module tab opens.")
    print("3. Once you are inside the Student Module dashboard, press ENTER below!")
    print("--------------------\n")

    input("Press ENTER in this PowerShell window once the Student Module page is loaded...")

    try:
        # 1. Switch to the Student Module tab (or newest open tab)
        school_id = None
        for handle in reversed(driver.window_handles):
            driver.switch_to.window(handle)
            curr_url = driver.current_url or ""
            m = re.search(r'/school/(\d+)/', curr_url)
            if m:
                school_id = m.group(1)
                print(f"\nSwitched to Student Module tab! Detected internal schoolId: {school_id}")
                break

        if not school_id and len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(1)
            m = re.search(r'/school/(\d+)/', driver.current_url or "")
            if m:
                school_id = m.group(1)

        # Read 11-digit UDISE code from the page header if visible
        udise_code = "School"
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            u_match = re.search(r'UDISE\s*Code\s*:\s*(\d{11})', body_text)
            if u_match:
                udise_code = u_match.group(1)
                print(f"Detected School UDISE Code: {udise_code}")
        except Exception:
            pass

        all_records = []

        # 2. Pull complete student profiles (Active List + General Profile Form 1)
        if school_id:
            print("\nStep 1/2: Fetching all students & General Profiles (GP) from UDISE+...")
            driver.execute_script(JS_INSTALL_XHR_SPY)
            driver.get(f"https://sdms.udiseplus.gov.in/g1/#/school/{school_id}/listAllStudentCy")
            time.sleep(2)
            driver.execute_script(JS_INSTALL_XHR_SPY)
            time.sleep(4)

            driver.set_script_timeout(180)
            api_res = driver.execute_async_script(JS_FETCH_ALL_STUDENTS_AND_GP, school_id)

            if isinstance(api_res, dict) and api_res.get("ok") and api_res.get("records"):
                print(f"  -> Pulled {api_res.get('count')} full Student General Profiles via UDISE+ API!")
                all_records = parse_api_records(api_res["records"])
            else:
                print(f"  -> API notice ({api_res}). Using Table Scraper...")

        # 3. Enrich with Active Students table DOM (for Class labels, Aadhaar display, APAAR ID, etc.)
        print("Step 2/2: Cross-checking Active Students table for Aadhaar/APAAR/Class details...")
        dom_by_pen, dom_by_name_dob = scrape_active_students_table(driver, school_id)

        if not all_records:
            all_records = list(dom_by_pen.values()) if dom_by_pen else list(dom_by_name_dob.values())
        else:
            # Fill any blank fields in all_records using the DOM table values
            for r in all_records:
                dom_rec = dom_by_pen.get(r.get("PEN")) or dom_by_name_dob.get((r.get("Name"), r.get("Date of Birth")))
                if dom_rec:
                    for k, v in dom_rec.items():
                        if v and not r.get(k):
                            r[k] = v

        # 4. If Phone Numbers are still missing, enrich from APAAR Module
        has_phones = any(bool(r.get("Phone Number")) for r in all_records)
        if not has_phones and all_records:
            by_pen_map = {r["PEN"]: r for r in all_records if r.get("PEN")}
            by_nd_map = {(r["Name"], r["Date of Birth"]): r for r in all_records}
            scrape_apaar_module(driver, by_pen_map, by_nd_map)

        # 5. Save to Excel (No auto-upload — 100% ready for manual Excel upload!)
        if all_records:
            all_records = sort_and_assign_rolls(all_records)
            df = pd.DataFrame(all_records)

            output_filename = "All_Classes_Students.xlsx"
            df.to_excel(output_filename, index=False)

            udise_filename = f"UDISE_{udise_code}_Students.xlsx"
            df.to_excel(udise_filename, index=False)

            # Also generate Odia-ready Excel file automatically!
            odia_records = build_odia_records(all_records)
            df_odia = pd.DataFrame(odia_records)
            odia_filename = f"UDISE_{udise_code}_Students_ODIA.xlsx"
            df_odia.to_excel(odia_filename, index=False)

            total = len(all_records)
            with_father = sum(1 for r in all_records if r.get("Father's Name"))
            with_mother = sum(1 for r in all_records if r.get("Mother's Name"))
            with_phone = sum(1 for r in all_records if r.get("Phone Number"))
            with_addr = sum(1 for r in all_records if r.get("Address"))
            with_bg = sum(1 for r in all_records if r.get("Blood Group"))
            with_aadhaar = sum(1 for r in all_records if r.get("AADHAAR Number"))
            with_pen = sum(1 for r in all_records if r.get("PEN"))

            print("\n======================================================================")
            print(f" SUCCESS! Extracted {total} students into Excel!")
            print(f"   - PEN Number       : {with_pen}/{total}")
            print(f"   - AADHAAR Number   : {with_aadhaar}/{total}")
            print(f"   - Father's Name    : {with_father}/{total}")
            print(f"   - Mother's Name    : {with_mother}/{total}")
            print(f"   - Phone Number     : {with_phone}/{total}")
            print(f"   - Address/Pincode  : {with_addr}/{total}")
            print(f"   - Blood Group      : {with_bg}/{total}")
            print("----------------------------------------------------------------------")
            print(" Saved Excel Files (in your current folder):")
            print(f"   1. {os.path.abspath(output_filename)} (English)")
            print(f"   2. {os.path.abspath(udise_filename)} (English)")
            print(f"   3. {os.path.abspath(odia_filename)} (Odia Class/Digits + English Blood Group!)")
            print("======================================================================")
        else:
            print("\nNo records were found. Make sure you are logged into the UDISE+ Student Module tab.")

    except Exception:
        print("\nAn error occurred during extraction:")
        traceback.print_exc()

    finally:
        input("\nPress ENTER to close the browser and exit...")
        driver.quit()

if __name__ == "__main__":
    automate_and_scrape()
