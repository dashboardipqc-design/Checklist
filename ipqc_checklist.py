import streamlit as st
from supabase import create_client
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import uuid
import time


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="IPQC Audit Checklist",
    page_icon="📋",
    layout="wide"
)

# =========================================================
# HEADER
# =========================================================

header_title, header_finding = st.columns(
    [8, 1]
)

with header_title:

    st.title(
        "📋 IPQC Audit Checklist"
    )


with header_finding:

    st.markdown(
        "<div style='height: 35px;'></div>",
        unsafe_allow_html=True
    )

    st.link_button(
        "Finding",
        "https://ipqcfinding.streamlit.app/",
        width="stretch"
    )

# =========================================================
# COMPACT CHECKLIST UI
# =========================================================

st.markdown(
    """
    <style>

    /* Reduce normal paragraph spacing */
    div[data-testid="stMarkdownContainer"] p {
        margin-bottom: 0.20rem;
    }

    /* Compact radio buttons */
    div[role="radiogroup"] {
        margin-top: -0.20rem;
        margin-bottom: -0.35rem;
    }

    /* Compact divider */
    hr {
        margin-top: 0.65rem !important;
        margin-bottom: 0.65rem !important;
    }

    /* Slightly reduce vertical block spacing */
    div[data-testid="stVerticalBlock"] {
        gap: 0.45rem;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# SUPABASE CONNECTION
# =========================================================

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# TIMEZONE
# =========================================================

MALAYSIA_TZ = ZoneInfo("Asia/Kuala_Lumpur")


# =========================================================
# GET ACTIVE CHECKLISTS
# =========================================================

master_response = (
    supabase
    .table("checklist_master")
    .select("*")
    .eq("active", True)
    .execute()
)

checklists = master_response.data

if not checklists:
    st.warning("No active checklist found.")
    st.stop()


# =========================================================
# FACTORY SELECTION
# =========================================================

factory = st.selectbox(
    "Factory",
    [
        "",
        "BKF",
        "BLF",
        "SPF"
    ]
)

if not factory:
    st.stop()


# =========================================================
# AREA SELECTION
# =========================================================

AREA_ORDER = [
    "DP",
    "FOL",
    "MOL",
    "EOL"
]

available_areas = {
    row["area"]
    for row in checklists
}

areas = [
    area_name
    for area_name in AREA_ORDER
    if area_name in available_areas
]

area = st.selectbox(
    "Area",
    [""] + areas
)

if not area:
    st.stop()

# =========================================================
# SHIFT DATE
# =========================================================

def get_shift_date(dt):

    current_minutes = (
        dt.hour * 60
        + dt.minute
    )

    morning_cutoff = (
        6 * 60 + 30
    )

    # 00:00 - 06:29 belongs to previous day's night shift
    if current_minutes < morning_cutoff:

        return (
            dt.date()
            - timedelta(days=1)
        )

    return dt.date()


# =========================================================
# DAY / NIGHT
# =========================================================

def get_day_night(dt):

    current_minutes = (
        dt.hour * 60
        + dt.minute
    )

    day_start = (
        6 * 60 + 30
    )

    night_start = (
        18 * 60 + 30
    )

    # DAY = 06:30 - 18:29
    if (
        day_start
        <= current_minutes
        < night_start
    ):

        return "DAY"

    # NIGHT = 18:30 - 06:29
    return "NIGHT"


# =========================================================
# A / B / C / D CREW CALCULATION
# =========================================================

def get_roster_crew(
    shift_date,
    shift_type
):

    # Reference from supplied roster:
    # 22-Sep-2026
    # DAY   = B
    # NIGHT = A

    anchor_date = date(
        2026,
        9,
        22
    )

    days_difference = (
        shift_date
        - anchor_date
    ).days

    # 14-day DAY roster cycle
    day_cycle = [
        "B",
        "B",
        "B",
        "B",
        "C",
        "C",
        "C",
        "A",
        "A",
        "A",
        "A",
        "D",
        "D",
        "D"
    ]

    # 14-day NIGHT roster cycle
    night_cycle = [
        "A",
        "A",
        "A",
        "A",
        "D",
        "D",
        "D",
        "B",
        "B",
        "B",
        "B",
        "C",
        "C",
        "C"
    ]

    cycle_position = (
        days_difference
        % 14
    )

    if shift_type == "DAY":

        return day_cycle[
            cycle_position
        ]

    return night_cycle[
        cycle_position
    ]

# =========================================================
# CURRENT OPERATIONAL SHIFT FOR PROCESS STATUS
# =========================================================

status_datetime = datetime.now(MALAYSIA_TZ)

status_shift_date = get_shift_date(
    status_datetime
)

status_shift_type = get_day_night(
    status_datetime
)

status_crew = get_roster_crew(
    status_shift_date,
    status_shift_type
)

status_shift = (
    f"{status_crew} - {status_shift_type}"
)
# =========================================================
# GET CURRENT SHIFT PROCESS SUBMISSION STATUS
# =========================================================

process_status_response = (
    supabase
    .table("inspection_header")
    .select("checklist_id, submission_type")
    .eq("factory", factory)
    .eq("shift_date", status_shift_date.isoformat())
    .eq("shift", status_shift)
    .eq("status", "SUBMITTED")
    .execute()
)

process_status_records = (
    process_status_response.data
    or []
)


# ---------------------------------------------------------
# NOT RUNNING PROCESSES
# ---------------------------------------------------------

status_not_running_processes = {
    row["checklist_id"]
    for row in process_status_records
    if row.get("submission_type") == "NOT_RUNNING"
}


# ---------------------------------------------------------
# NORMALLY COMPLETED PROCESSES
# ---------------------------------------------------------

status_completed_processes = {
    row["checklist_id"]
    for row in process_status_records
    if row.get("submission_type") == "NORMAL"
}


# ---------------------------------------------------------
# ADDITIONAL CREDIT AVAILABLE
# ---------------------------------------------------------

status_additional_used = sum(
    1
    for row in process_status_records
    if row.get("submission_type") == "ADDITIONAL"
)

status_additional_available = max(
    len(status_not_running_processes)
    - status_additional_used,
    0
)
# =========================================================
# PROCESS SELECTION
# =========================================================

area_checklists = [
    row
    for row in checklists
    if row["area"] == area
]


# ---------------------------------------------------------
# BUILD PROCESS DISPLAY NAMES
# ---------------------------------------------------------

process_display_map = {}
process_sort_map = {}

for row in area_checklists:

    process_name = row["process"]
    process_checklist_id = row["id"]


    # -----------------------------------------------------
    # NOT RUNNING
    # Priority 3
    # -----------------------------------------------------

    if process_checklist_id in status_not_running_processes:

        display_name = (
            f"🔴 {process_name}"
        )

        status_priority = 3


    # -----------------------------------------------------
    # SUBMITTED
    # Priority 2
    # -----------------------------------------------------

    elif (
        process_checklist_id in status_completed_processes
        and
        status_additional_available <= 0
    ):

        display_name = (
            f"🟢 {process_name}"
        )

        status_priority = 2


    # -----------------------------------------------------
    # AVAILABLE TO SUBMIT
    # Includes additional-credit availability
    # Priority 1
    # -----------------------------------------------------

    else:

        display_name = (
            f"⚪ {process_name}"
        )

        status_priority = 1


    process_display_map[
        display_name
    ] = process_name

    process_sort_map[
        display_name
    ] = status_priority


# ---------------------------------------------------------
# SORT BY STATUS, THEN PROCESS NAME
# ---------------------------------------------------------

process_display_options = sorted(
    process_display_map.keys(),
    key=lambda display_name: (
        process_sort_map[display_name],
        process_display_map[display_name]
    )
)


# ---------------------------------------------------------
# PROCESS DROPDOWN
# ---------------------------------------------------------

selected_process_display = st.selectbox(
    "Process",
    [""] + process_display_options
)

if not selected_process_display:
    st.stop()


# ---------------------------------------------------------
# CONVERT DISPLAY NAME BACK TO REAL PROCESS NAME
# ---------------------------------------------------------

process = process_display_map[
    selected_process_display
]
# =========================================================
# FIND SELECTED CHECKLIST
# =========================================================

selected_checklist = next(
    row
    for row in area_checklists
    if row["process"] == process
)

checklist_id = selected_checklist["id"]


# =========================================================
# GET ACTIVE REVISION
# =========================================================

version_response = (
    supabase
    .table("checklist_versions")
    .select("*")
    .eq("checklist_id", checklist_id)
    .eq("active", True)
    .execute()
)

versions = version_response.data

if not versions:
    st.error("No active checklist revision found.")
    st.stop()

version = versions[0]

version_id = version["id"]
revision = version["revision"]


# =========================================================
# GET CHECKLIST ITEMS
# =========================================================

items_response = (
    supabase
    .table("checklist_items")
    .select("*")
    .eq("version_id", version_id)
    .eq("active", True)
    .order("sequence")
    .execute()
)

items = items_response.data

if not items:
    st.warning("No checklist items found.")
    st.stop()


# =========================================================
# INSPECTION START DATE / TIME
# =========================================================

inspection_session_key = (
    f"{factory}_{checklist_id}_{version_id}"
)

if (
    "inspection_session_key"
    not in st.session_state
    or
    st.session_state.inspection_session_key
    != inspection_session_key
):

    st.session_state.inspection_session_key = (
        inspection_session_key
    )

    st.session_state.inspection_start_time = (
        datetime.now(MALAYSIA_TZ)
    )

inspection_datetime = (
    st.session_state.inspection_start_time
)

# =========================================================
# CALCULATE CURRENT SHIFT
# =========================================================

shift_date = get_shift_date(
    inspection_datetime
)

shift_type = get_day_night(
    inspection_datetime
)

crew = get_roster_crew(
    shift_date,
    shift_type
)

shift = (
    f"{crew} - {shift_type}"
)

# =========================================================
# SUBMISSION SESSION STATE
# =========================================================

submission_lock_key = (
    f"submission_locked_"
    f"{factory}_"
    f"{checklist_id}_"
    f"{shift_date}_"
    f"{shift}"
)

submission_locked = st.session_state.get(
    submission_lock_key,
    False
)

# =========================================================
# CHECK CURRENT SHIFT SUBMISSION
# =========================================================

current_shift_response = (
    supabase
    .table("inspection_header")
    .select("id, inspection_no")
    .eq("factory", factory)
    .eq("checklist_id", checklist_id)
    .eq("shift_date", shift_date.isoformat())
    .eq("shift", shift)
    .eq("submission_type", "NORMAL")
    .eq("status", "SUBMITTED")
    .execute()
)

normal_submission_exists = bool(
    current_shift_response.data
)

# =========================================================
# CHECK IF PROCESS ALREADY MARKED NOT RUNNING
# =========================================================

not_running_response = (
    supabase
    .table("inspection_header")
    .select("id, inspection_no")
    .eq("factory", factory)
    .eq("checklist_id", checklist_id)
    .eq("shift_date", shift_date.isoformat())
    .eq("shift", shift)
    .eq("submission_type", "NOT_RUNNING")
    .eq("status", "SUBMITTED")
    .execute()
)

process_already_not_running = bool(
    not_running_response.data
)
# =========================================================
# ADDITIONAL SUBMISSION CREDIT
# =========================================================

shift_submission_response = (
    supabase
    .table("inspection_header")
    .select("id, checklist_id, submission_type")
    .eq("factory", factory)
    .eq("shift_date", shift_date.isoformat())
    .eq("shift", shift)
    .eq("status", "SUBMITTED")
    .execute()
)

shift_submission_records = (
    shift_submission_response.data
    or []
)


# ---------------------------------------------------------
# COUNT UNIQUE NOT RUNNING PROCESSES
# ---------------------------------------------------------

not_running_processes = {
    row["checklist_id"]
    for row in shift_submission_records
    if row.get("submission_type") == "NOT_RUNNING"
}

not_running_count = len(
    not_running_processes
)


# ---------------------------------------------------------
# COUNT ADDITIONAL SUBMISSIONS ALREADY USED
# ---------------------------------------------------------

additional_used = sum(
    1
    for row in shift_submission_records
    if row.get("submission_type") == "ADDITIONAL"
)


# ---------------------------------------------------------
# CALCULATE AVAILABLE ADDITIONAL CREDIT
# ---------------------------------------------------------

additional_available = max(
    not_running_count - additional_used,
    0
)
# =========================================================
# BLOCK PROCESS ALREADY MARKED NOT RUNNING
# =========================================================

if process_already_not_running:

    st.warning(
        f"🔴 Process Not Running. This process has been marked not running for the current shift."
    )

    st.stop()
# =========================================================
# DETERMINE SUBMISSION MODE
# =========================================================

submission_mode = "NORMAL"


if normal_submission_exists:

    # -----------------------------------------------------
    # ADDITIONAL SUBMISSION AVAILABLE
    # -----------------------------------------------------

    if additional_available > 0:

        submission_mode = "ADDITIONAL"

        # Previous NORMAL submission lock belongs to the
        # earlier inspection, not this new ADDITIONAL one.
        st.session_state.pop(
            submission_lock_key,
            None
        )

        submission_locked = False

        st.success(
            "⚪ Additional Submission."
        )


    # -----------------------------------------------------
    # CHECKLIST ALREADY COMPLETED
    # -----------------------------------------------------

    else:

        st.error(
            "🟢 Checklist Completed. "
            "This process has already been submitted for the current shift."
        )

        st.stop()
    
# =========================================================
# INSPECTION INFORMATION
# =========================================================

st.divider()

# =========================================================
# PROCESS RUNNING STATUS
# =========================================================

if submission_mode == "ADDITIONAL":

    process_status = "Running"

else:

    process_status = st.radio(
        "Process Status",
        [
            "Running",
            "Not Running"
        ],
        horizontal=True,
        key=f"process_status_{factory}_{checklist_id}_{shift_date}_{shift}"
    )

# =========================================================
# NOT RUNNING PROCESS
# =========================================================

if process_status == "Not Running":

    st.warning(
        f"{process} is marked as NOT RUNNING "
        f"for the current shift."
    )

    not_running_inspector = st.text_input(
        "Inspector Badge",
        placeholder="e.g. 505641",
        key=f"not_running_inspector_{checklist_id}"
    )

    confirm_not_running = st.button(
        "Confirm Not Running",
        type="primary",
        use_container_width=True
    )

    if confirm_not_running:

        if not not_running_inspector.strip():

            st.error(
                "Please enter Inspector Badge."
            )

        else:

            try:

                # -------------------------------------------------
                # CHECK IF ALREADY MARKED NOT RUNNING
                # -------------------------------------------------

                existing_not_running = (
                    supabase
                    .table("inspection_header")
                    .select("id")
                    .eq("factory", factory)
                    .eq("checklist_id", checklist_id)
                    .eq("shift_date", shift_date.isoformat())
                    .eq("shift", shift)
                    .eq("submission_type", "NOT_RUNNING")
                    .execute()
                )

                if existing_not_running.data:

                    st.warning(
                        "This process has already been marked "
                        "Not Running for the current shift."
                    )

                else:

                    # -------------------------------------------------
                    # CREATE NOT RUNNING RECORD
                    # -------------------------------------------------

                    submitted_datetime = datetime.now(
                        MALAYSIA_TZ
                    )

                    inspection_no = (
                        "NR-"
                        + submitted_datetime.strftime("%Y%m%d-%H%M%S")
                        + "-"
                        + uuid.uuid4().hex[:6].upper()
                    )

                    not_running_header = {
                        "inspection_no": inspection_no,
                        "factory": factory,
                        "checklist_id": checklist_id,
                        "version_id": version_id,
                        "lot_number": "",
                        "machine": "",
                        "inspector": not_running_inspector.strip(),
                        "shift": shift,
                        "shift_date": shift_date.isoformat(),
                        "submission_type": "NOT_RUNNING",
                        "inspection_datetime": inspection_datetime.isoformat(),
                        "status": "SUBMITTED",
                        "submitted_at": submitted_datetime.isoformat()
                    }

                    (
                        supabase
                        .table("inspection_header")
                        .insert(not_running_header)
                        .execute()
                    )

                    st.success(
                        f"{process} successfully recorded "
                        f"as Not Running for this shift."
                    )

                    st.info(
                        "1 additional checklist submission "
                        "has been generated for this shift."
                    )

                    st.rerun()

            except Exception as e:

                error_message = str(e)

                if (
                    "uq_inspection_header_not_running"
                    in error_message
                ):

                    st.warning(
                        "🔴 Process Not Running. "
                        "This process has already been marked "
                        "Not Running for the current shift."
                    )

                else:

                    st.error(
                        "Unable to save Not Running status. "
                        "Please try again or contact Quality "
                        "Engineering if the problem continues."
                    )

    st.stop()
    
st.subheader(
    selected_checklist["checklist_name"]
)

st.caption(
    f"Factory: {factory}  |  "
    f"Area: {area}  |  "
    f"Process: {process}  |  "
    f"Revision: {revision}"
)


# =========================================================
# AUTOMATIC DATE / TIME & SHIFT
# =========================================================

col_dt, col_shift = st.columns(
    [2, 1]
)

with col_dt:

    st.text_input(
        "Inspection Date & Time",
        value=inspection_datetime.strftime(
            "%d-%b-%Y %H:%M:%S"
        ),
        disabled=True
    )

with col_shift:

    st.text_input(
        "Shift",
        value=shift,
        disabled=True
    )


# =========================================================
# LOT / MACHINE / INSPECTOR / AUDITEE
# =========================================================

col1, col2, col3, col4 = st.columns(4)

with col1:

    lot_number = st.text_input(
        "Lot Number",
        placeholder="e.g. WCA5225"
    )

with col2:

    machine = st.text_input(
        "Machine / Workstation Number",
        placeholder="e.g. ICO-01"
    )

with col3:

    inspector = st.text_input(
        "Inspector Badge",
        placeholder="e.g. 505641"
    )

with col4:

    auditee = st.text_input(
        "Auditee Badge",
        placeholder="e.g. 505641"
    )

# =========================================================
# CHECKLIST FORM
# =========================================================

st.divider()

current_section = None

answers = {}

finding_entries = {}

finding_categories = [
    "Method / Handling - Incorrect process execution, setup, or operating method",
    "Machine / Facility - Ionizer, machine abnormal reading, equipment/facility condition",
    "Man / Personnel Compliance - Not following cleanroom, 5S, ESD, discipline requirement",
    "Material / Product - Material condition, expiry, identification, mixed material",
    "Document / Record - Checklist, record, label, traceability, or documentation"
]


for item in items:

    # -----------------------------------------------------
    # SECTION HEADER
    # -----------------------------------------------------

    if (
        item["section_code"]
        != current_section
    ):

        current_section = (
            item["section_code"]
        )

        st.markdown(
            f"### "
            f"{item['section_code']}. "
            f"{item['section_name']}"
        )


    # -----------------------------------------------------
    # ITEM INFORMATION
    # -----------------------------------------------------

    item_id = (
        item["id"]
    )

    item_code = (
        item["item_code"]
    )

    description = (
        item["item_description"]
    )

    input_type = (
        item["input_type"]
    )

    reference_image_path = (
        item.get(
            "reference_image_path"
        )
    )


    # =====================================================
    # ITEM DESCRIPTION + REFERENCE IMAGE
    # =====================================================

    if reference_image_path:

        item_col, reference_col = st.columns(
            [5, 1]
        )

        with item_col:

            st.markdown(
                f"**{item_code} - {description}**"
            )

        with reference_col:

            show_reference = st.toggle(
                "📷 View Reference",
                key=f"reference_{item_id}"
            )


        if show_reference:

            reference_image_url = (
                supabase
                .storage
                .from_(
                    "checklist-reference"
                )
                .get_public_url(
                    reference_image_path
                )
            )

            st.image(
                reference_image_url,
                caption="IPQC Inspection Reference",
                width=500
            )


    else:

        st.markdown(
            f"**{item_code} - {description}**"
        )


    # -----------------------------------------------------
    # PASS / FAIL / N/A
    # -----------------------------------------------------

    if input_type == "PASS_FAIL_NA":

        answers[item_id] = {

            "type":
                "PASS_FAIL_NA",

            "value":
                st.radio(
                    "Result",
                    [
                        "Pass",
                        "Fail",
                        "N/A"
                    ],
                    index=None,
                    horizontal=True,
                    key=f"result_{item_id}",
                    label_visibility="collapsed"
                )
        }


    # -----------------------------------------------------
    # TEXT
    # -----------------------------------------------------

    elif input_type == "TEXT":

        answers[item_id] = {

            "type":
                "TEXT",

            "value":
                st.text_input(
                    description,
                    key=f"text_{item_id}",
                    label_visibility="collapsed"
                )
        }


    # -----------------------------------------------------
    # DATE
    # -----------------------------------------------------

    elif input_type == "DATE":

        answers[item_id] = {

            "type":
                "DATE",

            "value":
                st.date_input(
                    description,
                    value=None,
                    key=f"date_{item_id}",
                    label_visibility="collapsed"
                )
        }


    # =====================================================
    # FINDING INFORMATION
    # Display directly below the failed checklist item
    # =====================================================

    if (
        input_type == "PASS_FAIL_NA"
        and
        answers[item_id]["value"] == "Fail"
    ):

        with st.container(border=True):

            st.markdown(
                f"#### ⚠ Finding — {item_code}"
            )

            category = st.selectbox(
                "Category",
                [""] + finding_categories,
                key=f"finding_category_{item_id}"
            )

            finding_description = st.text_area(
                "Finding Description",
                placeholder=(
                    "During [when], [what] was observed at [where]. "
                    "This does not meet [requirement]. "
                    "Acknowledged by [supervisor/leader]."
                ),
                height=90,
                key=f"finding_description_{item_id}"
            )

            interview_result = st.text_area(
                "Interview Result",
                placeholder=(
                    "Enter explanation from auditee or supervisor"
                ),
                height=90,
                key=f"finding_interview_{item_id}"
            )

            containment_action = st.text_area(
                "Containment Action",
                placeholder=(
                    "Enter immediate containment action taken"
                ),
                height=90,
                key=f"finding_containment_{item_id}"
            )

            finding_entries[item_id] = {
                "item_code":
                    item_code,

                "item_description":
                    description,

                "category":
                    category,

                "finding_description":
                    finding_description,

                "interview_result":
                    interview_result,

                "containment_action":
                    containment_action
            }


    # -----------------------------------------------------
    # COMPACT ITEM DIVIDER
    # -----------------------------------------------------

    st.markdown(
        "<hr>",
        unsafe_allow_html=True
    )

# =========================================================
# FAILED CHECKLIST ITEMS
# Used for validation and Finding submission
# =========================================================

failed_items_current = [

    item
    for item in items

    if (
        answers.get(item["id"], {}).get("type")
        == "PASS_FAIL_NA"

        and

        answers.get(item["id"], {}).get("value")
        == "Fail"
    )
]

# =========================================================
# SUBMIT INSPECTION
# =========================================================



# =========================================================
# SUBMIT BUTTON
# =========================================================

submit_button_placeholder = st.empty()

submit_inspection = submit_button_placeholder.button(
    "Submitted ✓" if submission_locked else "Submit Inspection",
    type="primary",
    use_container_width=True,
    disabled=submission_locked,
    key="submit_inspection_button"
)


if submit_inspection:

    # =====================================================
    # BLOCK DUPLICATE SUBMISSION FROM SAME LOADED PAGE
    # =====================================================

    if st.session_state.get(
        submission_lock_key,
        False
    ):

        st.error(
            "This inspection has already been submitted."
        )

        st.stop()

    # =====================================================
    # RECHECK ADDITIONAL CREDIT BEFORE SUBMISSION
    # =====================================================

    if submission_mode == "ADDITIONAL":

        latest_shift_response = (
            supabase
            .table("inspection_header")
            .select("id, checklist_id, submission_type")
            .eq("factory", factory)
            .eq("shift_date", shift_date.isoformat())
            .eq("shift", shift)
            .eq("status", "SUBMITTED")
            .execute()
        )

        latest_shift_records = (
            latest_shift_response.data
            or []
        )

        latest_not_running_processes = {
            row["checklist_id"]
            for row in latest_shift_records
            if row.get("submission_type") == "NOT_RUNNING"
        }

        latest_additional_used = sum(
            1
            for row in latest_shift_records
            if row.get("submission_type") == "ADDITIONAL"
        )

        latest_additional_available = max(
            len(latest_not_running_processes)
            - latest_additional_used,
            0
        )

        if latest_additional_available <= 0:

            st.error(
                "Additional submission credit is no longer available. "
                "Please refresh the checklist."
            )

            st.stop()


    # =====================================================
    # VALIDATE HEADER
    # =====================================================

    missing_header = []
    invalid_header = []

    if not lot_number.strip():

        missing_header.append(
            "Lot Number"
        )

    if not machine.strip():

        missing_header.append(
            "Machine"
        )

    if not inspector.strip():

        missing_header.append(
            "Inspector Badge"
        )

    elif (
        not inspector.strip().isdigit()
        or
        len(inspector.strip()) != 6
    ):

        invalid_header.append(
            "Inspector Badge must be six (6) numerical digits."
        )


    if not auditee.strip():

        missing_header.append(
            "Auditee Badge"
        )

    elif (
        not auditee.strip().isdigit()
        or
        len(auditee.strip()) != 6
    ):

        invalid_header.append(
            "Auditee Badge must be six (6) numerical digits."
        )
        
    # =====================================================
    # VALIDATE CHECKLIST
    # =====================================================

    missing_items = []

    for item in items:

        if item["required"]:

            answer = answers.get(
                item["id"]
            )

            if not answer:

                missing_items.append(
                    item["item_code"]
                )

                continue

            value = answer["value"]

            if (
                value is None
                or
                value == ""
            ):

                missing_items.append(
                    item["item_code"]
                )

    # =====================================================
    # VALIDATE FINDING INFORMATION
    # =====================================================

    missing_finding_fields = []


    for failed_item in failed_items_current:

        failed_item_id = failed_item["id"]
        failed_item_code = failed_item["item_code"]

        finding_entry = finding_entries.get(
            failed_item_id,
            {}
        )


        if not finding_entry.get(
            "category",
            ""
        ).strip():

            missing_finding_fields.append(
                f"{failed_item_code} - Category"
            )


        if not finding_entry.get(
            "finding_description",
            ""
        ).strip():

            missing_finding_fields.append(
                f"{failed_item_code} - Finding Description"
            )


        if not finding_entry.get(
            "interview_result",
            ""
        ).strip():

            missing_finding_fields.append(
                f"{failed_item_code} - Interview Result"
            )


        if not finding_entry.get(
            "containment_action",
            ""
        ).strip():

            missing_finding_fields.append(
                f"{failed_item_code} - Containment Action"
            )


    # =====================================================
    # SHOW VALIDATION ERRORS
    # =====================================================

    if missing_header:

        st.error(
            "Please complete the inspection information: "
            + ", ".join(
                missing_header
            )
        )


    elif invalid_header:

        st.error(
            " ".join(
                invalid_header
            )
        )


    elif missing_items:

        st.error(
            "Please complete all required checklist items."
        )

        st.write(
            "Missing:",
            ", ".join(
                missing_items
            )
        )


    elif missing_finding_fields:

        st.error(
            "Please complete all Finding information "
            "for the failed checklist item(s)."
        )

        st.write(
            "Missing:",
            ", ".join(
                missing_finding_fields
            )
        )
    # =====================================================
    # SAVE INSPECTION
    # =====================================================

    else:

        try:

            # =================================================
            # SUBMISSION DATE / TIME
            # =================================================

            submitted_datetime = (
                datetime.now(
                    MALAYSIA_TZ
                )
            )


            # =================================================
            # GENERATE UNIQUE INSPECTION NUMBER
            # =================================================

            short_id = (
                uuid.uuid4()
                .hex[:6]
                .upper()
            )

            inspection_no = (
                f"INS-"
                f"{submitted_datetime.strftime('%Y%m%d-%H%M%S')}-"
                f"{short_id}"
            )

            # =================================================
            # PREPARE INSPECTION RESULTS
            # =================================================

            result_rows = []

            for item in items:

                item_id = item["id"]
                answer = answers[item_id]
                input_type = answer["type"]
                value = answer["value"]

                result_row = {

                    "item_id":
                        item_id,

                    "result":
                        None,

                    "text_value":
                        None,

                    "numeric_value":
                        None,

                    "date_value":
                        None,

                    "remark":
                        None
                }

                if input_type == "PASS_FAIL_NA":

                    result_row[
                        "result"
                    ] = value

                elif input_type == "TEXT":

                    result_row[
                        "text_value"
                    ] = value

                elif input_type == "DATE":

                    result_row[
                        "date_value"
                    ] = (
                        value.isoformat()
                        if value
                        else None
                    )

                result_rows.append(
                    result_row
                )
            # =================================================
            # PREPARE FINDINGS FOR FAILED CHECKLIST ITEMS
            # =================================================

            finding_rows = []


            for failed_item in failed_items_current:

                failed_item_id = failed_item["id"]

                finding_entry = finding_entries[
                    failed_item_id
                ]


                finding_rows.append(
                    {
                        "area":
                            area,

                        "station":
                            process,

                        "auditee":
                            auditee.strip(),

                        "item_code":
                            failed_item["item_code"],

                        "item_description":
                            failed_item["item_description"],

                        "category":
                            finding_entry["category"].strip(),

                        "finding_description":
                            finding_entry[
                                "finding_description"
                            ].strip(),

                        "interview_result":
                            finding_entry[
                                "interview_result"
                            ].strip(),

                        "containment_action":
                            finding_entry[
                                "containment_action"
                            ].strip()
                    }
                )

            # =================================================
            # ATOMIC DATABASE SUBMISSION
            # Header + Results are saved in one transaction.
            # Additional credit is validated and consumed
            # inside PostgreSQL.
            # =================================================

            rpc_response = (
                supabase
                .rpc(
                    "submit_ipqc_inspection",
                    {
                        "p_inspection_no":
                            inspection_no,

                        "p_factory":
                            factory,

                        "p_checklist_id":
                            checklist_id,

                        "p_version_id":
                            version_id,

                        "p_lot_number":
                            lot_number.strip(),

                        "p_machine":
                            machine.strip(),

                        "p_inspector":
                            inspector.strip(),

                        "p_shift":
                            shift,

                        "p_shift_date":
                            shift_date.isoformat(),

                        "p_submission_type":
                            submission_mode,

                        "p_inspection_datetime":
                            inspection_datetime.isoformat(),

                        "p_submitted_at":
                            submitted_datetime.isoformat(),

                        "p_results":
                            result_rows,

                        "p_findings":
                            finding_rows
                    }
                )
                .execute()
            )


            # =================================================
            # VERIFY DATABASE SUBMISSION
            # =================================================

            if not rpc_response.data:

                raise Exception(
                    "Inspection was not created."
                )


            # =================================================
            # LOCK SUCCESSFULLY SUBMITTED CHECKLIST
            # PREVENT DUPLICATE SUBMISSION FROM SAME PAGE
            # =================================================

            st.session_state[
                submission_lock_key
            ] = True

            # =================================================
            # SUBMISSION SUCCESS
            # Checklist + Results + Findings are already saved
            # atomically by PostgreSQL.
            # =================================================

            if failed_items_current:

                st.success(
                    f"Inspection submitted successfully. "
                    f"{len(failed_items_current)} Finding"
                    f"{'s' if len(failed_items_current) != 1 else ''} "
                    f"created."
                )

            else:

                st.success(
                    "Inspection submitted successfully."
                )


            time.sleep(1)


            st.session_state.pop(
                "inspection_session_key",
                None
            )

            st.session_state.pop(
                "inspection_start_time",
                None
            )


            st.rerun()


        except Exception as e:

            error_message = str(e)

            # =================================================
            # DUPLICATE NORMAL SUBMISSION
            # Another device submitted the checklist first
            # =================================================

            if (
                "uq_inspection_header_normal_submission"
                in error_message
            ):

                st.warning(
                    "🟢 Checklist Completed. "
                    "This process has already been submitted "
                    "for the current shift."
                )


            # =================================================
            # ADDITIONAL CREDIT ALREADY CONSUMED
            # Another device used the available credit first
            # =================================================

            elif (
                "NO_ADDITIONAL_CREDIT"
                in error_message
            ):

                st.warning(
                    "⚠️ Additional submission credit is no "
                    "longer available. Another submission may "
                    "have used the available credit."
                )


            # =================================================
            # OTHER UNEXPECTED ERROR
            # =================================================

            else:

                st.error(
                    "Unable to submit inspection. "
                    "Please try again or contact Quality "
                    "Engineering if the problem continues."
                )
