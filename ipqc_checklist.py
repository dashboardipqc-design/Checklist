import streamlit as st
from supabase import create_client
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import uuid


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="IPQC Audit Checklist",
    page_icon="📋",
    layout="wide"
)

st.title("📋 IPQC Audit Checklist")


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
# PROCESS SELECTION
# =========================================================

area_checklists = [
    row
    for row in checklists
    if row["area"] == area
]

processes = sorted(
    list(
        set(
            row["process"]
            for row in area_checklists
        )
    )
)

process = st.selectbox(
    "Process",
    [""] + processes
)

if not process:
    st.stop()


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
# INSPECTION INFORMATION
# =========================================================

st.divider()

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
# LOT / MACHINE / INSPECTOR
# =========================================================

col1, col2, col3 = st.columns(3)

with col1:

    lot_number = st.text_input(
        "Lot Number"
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


# =========================================================
# CHECKLIST FORM
# =========================================================

st.divider()

current_section = None

answers = {}


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


    # -----------------------------------------------------
    # COMPACT ITEM DIVIDER
    # -----------------------------------------------------

    st.markdown(
        "<hr>",
        unsafe_allow_html=True
    )

# =========================================================
# SUBMIT INSPECTION
# =========================================================

if st.button(
    "Submit Inspection",
    type="primary",
    use_container_width=True
):

    # =====================================================
    # VALIDATE HEADER
    # Lot Number is optional
    # =====================================================

    missing_header = []


    if not machine.strip():

        missing_header.append(
            "Machine"
        )


    if not inspector.strip():

        missing_header.append(
            "Inspector Badge"
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


            value = (
                answer["value"]
            )


            if (
                value is None
                or
                value == ""
            ):

                missing_items.append(
                    item["item_code"]
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
            # INSERT INSPECTION HEADER
            # =================================================

            header_data = {

                "inspection_no":
                    inspection_no,

                "factory":
                    factory,

                "checklist_id":
                    checklist_id,

                "version_id":
                    version_id,

                "lot_number":
                    lot_number.strip(),

                "machine":
                    machine.strip(),

                "inspector":
                    inspector.strip(),

                "shift":
                    shift,
                
                "shift_date":
                    shift_date.isoformat(),

                "submission_type":
                    "NORMAL",
                
                "inspection_datetime":
                    inspection_datetime.isoformat(),

                "status":
                    "SUBMITTED",

                "submitted_at":
                    submitted_datetime.isoformat()
            }


            header_response = (
                supabase
                .table(
                    "inspection_header"
                )
                .insert(
                    header_data
                )
                .execute()
            )


            if not header_response.data:

                raise Exception(
                    "Inspection header was not created."
                )


            inspection_id = (
                header_response
                .data[0]["id"]
            )


            # =================================================
            # PREPARE INSPECTION RESULTS
            # =================================================

            result_rows = []


            for item in items:

                item_id = (
                    item["id"]
                )

                answer = (
                    answers[item_id]
                )

                input_type = (
                    answer["type"]
                )

                value = (
                    answer["value"]
                )


                result_row = {

                    "inspection_id":
                        inspection_id,

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


                # ---------------------------------------------
                # PASS / FAIL / N/A
                # ---------------------------------------------

                if (
                    input_type
                    == "PASS_FAIL_NA"
                ):

                    result_row[
                        "result"
                    ] = value


                # ---------------------------------------------
                # TEXT
                # ---------------------------------------------

                elif (
                    input_type
                    == "TEXT"
                ):

                    result_row[
                        "text_value"
                    ] = value


                # ---------------------------------------------
                # DATE
                # ---------------------------------------------

                elif (
                    input_type
                    == "DATE"
                ):

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
            # INSERT ALL RESULTS
            # =================================================

            (
                supabase
                .table(
                    "inspection_results"
                )
                .insert(
                    result_rows
                )
                .execute()
            )


            # =================================================
            # SUCCESS
            # =================================================

            st.success(
                "Inspection submitted successfully."
            )


            st.info(
                f"Inspection No: {inspection_no}"
            )


            st.write(
                f"{len(result_rows)} "
                "inspection results saved."
            )


            # =================================================
            # CHECK FOR FAILED ITEMS
            # =================================================

            failed_items = [

                item
                for item in items

                if (
                    answers[item["id"]]["type"]
                    == "PASS_FAIL_NA"

                    and

                    answers[item["id"]]["value"]
                    == "Fail"
                )
            ]


            # =================================================
            # FINDING ENTRY
            # =================================================

            if failed_items:

                st.warning(
                    f"{len(failed_items)} failed "
                    "checklist item(s) detected. "
                    "Please raise a finding."
                )


                for failed_item in failed_items:

                    st.write(
                        f"• "
                        f"{failed_item['item_code']} - "
                        f"{failed_item['item_description']}"
                    )


                st.link_button(
                    "Open IPQC Finding Entry",
                    "https://ipqcchecklist.streamlit.app/",
                    type="primary",
                    use_container_width=True
                )


        except Exception as e:

            st.error(
                "Unable to submit inspection."
            )

            st.exception(e)
