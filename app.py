import math
import uuid
from datetime import date

import pandas as pd
import streamlit as st

# -----------------------------
# Helpers
# -----------------------------
def clean_number(n: float):
    """Render integers without .0 (e.g., 20.0 -> 20)."""
    try:
        return int(n) if float(n).is_integer() else n
    except Exception:
        return n

def compute_fee(total_value: float, withdrawn: float, due_custom: float | None):
    """Business fee rules."""
    if due_custom is not None:
        return due_custom

    half_value = total_value / 2
    eps = 1e-6

    rules_half = {
        40.0: 20.0,
        45.0: 20.0,
        50.0: 25.0,
        52.5: 27.5,
        55.0: 25.0,
    }

    for hv, fee in rules_half.items():
        if math.isclose(half_value, hv, abs_tol=eps):
            return fee

    if math.isclose(total_value, 95.0, abs_tol=eps):
        return 22.5

    if int(total_value) % 10 == 5:
        return 32.5

    return 30.0

def as_row(worker_id, name, total, due, withdrawn, remaining, note=""):
    # Keep ID internally; never display it
    return {
        "ID": worker_id,
        "Worker": name,
        "Total": clean_number(total),
        "Due": clean_number(due),
        "Withdrawn": clean_number(withdrawn),
        "Remaining": clean_number(remaining),
        "Note": note,
    }

# -----------------------------
# App Config
# -----------------------------
st.set_page_config(page_title="CleanFoam", page_icon="✅", layout="wide")
st.title("CleanFoam")

# -----------------------------
# Session State
# -----------------------------
if "workers" not in st.session_state:
    st.session_state.workers: list[dict] = []

if "report_date" not in st.session_state:
    st.session_state.report_date = date.today()

# -----------------------------
# MAIN PAGE INPUTS (no sidebar, visible immediately)
# -----------------------------
st.subheader("Inputs")

row1_col1, row1_col2, row1_col3, row1_col4 = st.columns([1, 1, 1, 1])
with row1_col1:
    st.session_state.report_date = st.date_input("Date", value=st.session_state.report_date)
with row1_col2:
    name = st.text_input("Name")
with row1_col3:
    entry_type = st.radio("Entry Type", ("Standard", "CF"), horizontal=True)
with row1_col4:
    note_text = st.text_input("Note (optional)")

row2_col1, row2_col2, row2_col3, row2_col4 = st.columns([1, 1, 1, 1])
with row2_col1:
    total_value = st.number_input("Enter the total", min_value=0.0, step=0.5, format="%.2f")
with row2_col2:
    withdrawn_val = st.number_input("Enter the withdrawn", min_value=0.0, step=0.5, format="%.2f")
with row2_col3:
    due_custom_val = st.number_input("Enter custom Due (optional)", min_value=0.0, step=0.5, format="%.2f")
    due_custom = None if due_custom_val == 0.0 else due_custom_val
with row2_col4:
    add_clicked = st.button("Add", type="primary", use_container_width=True)

row3_col1, _ = st.columns([1, 3])
with row3_col1:
    reset_clicked = st.button("Reset Workers", use_container_width=True)

# -----------------------------
# Add Logic
# -----------------------------
if add_clicked:
    if not name:
        st.error("Please enter a name.")
    elif total_value <= 0:
        st.error("Total must be greater than 0.")
    else:
        wid = uuid.uuid4().hex[:8]
        if entry_type == "CF":
            st.session_state.workers.append(
                as_row(wid, name, total_value, "", "", "", note_text)
            )
        else:
            fee = compute_fee(total_value, withdrawn_val, due_custom)
            half_value = total_value / 2
            after_withdraw = half_value - withdrawn_val
            remaining = after_withdraw - fee
            st.session_state.workers.append(
                as_row(wid, name, total_value, fee, withdrawn_val, remaining, note_text)
            )
        st.success(f"Added {name}")

if reset_clicked:
    st.session_state.workers = []
    st.info("All workers cleared.")

# -----------------------------
# Table & Metrics
# -----------------------------
if st.session_state.workers:
    df_internal = pd.DataFrame(st.session_state.workers)

    # Display dataframe WITHOUT the internal ID
    df_display = df_internal[["Worker", "Total", "Due", "Withdrawn", "Remaining", "Note"]]

    st.subheader("Workers Table")
    st.caption(f"Date: {st.session_state.report_date.strftime('%Y-%m-%d')}")

    # Style: make Note column bold
    def highlight_note(val):
        return "font-weight: bold" if val else ""

    st.dataframe(
        df_display.style.applymap(highlight_note, subset=["Note"]),
        use_container_width=True,
    )

    # Totals — CF rows are ALWAYS included in totals
    numeric_total = df_internal["Total"].apply(lambda x: x if isinstance(x, (int, float)) else 0).sum()
    numeric_withdrawn = df_internal["Withdrawn"].apply(lambda x: x if isinstance(x, (int, float)) else 0).sum()
    numeric_remaining = df_internal["Remaining"].apply(lambda x: x if isinstance(x, (int, float)) else 0).sum()

    for_workers = numeric_withdrawn + numeric_remaining
    total_for_cleanfoam = numeric_total - for_workers
    display_total = numeric_total

    c1, c2, c3 = st.columns(3)
    c1.metric("Total", clean_number(display_total))
    c2.metric("For workers", clean_number(for_workers))
    c3.metric("For CleanFoam", clean_number(total_for_cleanfoam))

    # Actions (no ID visible in UI)
    with st.expander("Actions"):
        st.markdown("### Delete a worker")
        # Build user-friendly labels without exposing ID; handle duplicates with # numbering
        labels = []
        id_map = {}
        name_counts = {}
        for _, r in df_internal.iterrows():
            n = r["Worker"]
            name_counts[n] = name_counts.get(n, 0) + 1
            label = f"{n} #{name_counts[n]}" if name_counts[n] > 1 else n
            labels.append(label)
            id_map[label] = r["ID"]

        if labels:
            selected_label = st.selectbox("Select worker to delete", labels)
            if st.button("Delete", type="secondary"):
                sel_id = id_map[selected_label]
                st.session_state.workers = [w for w in st.session_state.workers if w["ID"] != sel_id]
                st.success(f"Deleted {selected_label}")

        # Download CSV without ID
        csv = df_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"cleanfoam_{st.session_state.report_date.strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
else:
    st.info("No workers added yet.")
