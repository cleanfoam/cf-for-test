import math
import uuid
from datetime import date
import pandas as pd
import streamlit as st

# -----------------------------
# Configuration
# -----------------------------
st.set_page_config(
    page_title="CleanFoam Pro",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.title("CleanFoam Pro")

# -----------------------------
# Session State Management
# -----------------------------
def initialize_session_state():
    """Initialize session state variables if they don't exist."""
    if "workers" not in st.session_state:
        st.session_state.workers: list[dict] = []
    if "report_date" not in st.session_state:
        st.session_state.report_date = date.today()
    # To manage which worker is being edited/deleted
    if "action_id" not in st.session_state:
        st.session_state.action_id = None

# -----------------------------
# Helper Functions
# -----------------------------
def clean_number(n):
    """Render integers without .0 and handle non-numeric types gracefully."""
    if isinstance(n, (int, float)):
        return int(n) if float(n).is_integer() else f"{n:.2f}"
    return n

def compute_fee(total_value: float, custom_due: float | None) -> float:
    """Calculate the fee based on business rules."""
    if custom_due is not None and custom_due > 0:
        return custom_due
    rules = {80.0: 20.0, 90.0: 20.0, 95.0: 22.5, 100.0: 25.0, 105.0: 27.5, 110.0: 25.0}
    fee = rules.get(total_value)
    if fee is not None:
        return fee
    if int(total_value) % 10 == 5:
        return 32.5
    return 30.0

def create_worker_row(worker_id, name, total, due, withdrawn, remaining, note="", entry_type="Standard"):
    """Factory for creating a worker data dictionary."""
    return {
        "ID": worker_id, "Worker": name, "Total": total, "Due": due,
        "Withdrawn": withdrawn, "Remaining": remaining, "Note": note, "EntryType": entry_type
    }

# -----------------------------
# UI: Sidebar
# -----------------------------
def show_sidebar():
    """Render all input widgets and settings in the sidebar."""
    with st.sidebar:
        st.header("Add New Entry")
        
        name = st.text_input("Worker Name", help="Enter the name of the worker.")
        total_value = st.number_input("Total Value", min_value=0.0, step=0.5, format="%.2f")
        withdrawn_val = st.number_input("Withdrawn Value", min_value=0.0, step=0.5, format="%.2f")
        entry_type = st.radio("Entry Type", ("Standard", "CF"), horizontal=True, index=0)
        
        with st.expander("Advanced Options"):
            due_custom_val = st.number_input("Custom Due (Optional)", min_value=0.0, step=0.5, format="%.2f")
            note_text = st.text_input("Note (Optional)", help="Add any relevant notes.")

        if st.button("Add Worker", type="primary", use_container_width=True):
            if not name:
                st.sidebar.error("Worker name is required.")
            elif total_value <= 0 and entry_type == "Standard":
                st.sidebar.error("Total value must be greater than 0.")
            else:
                wid = uuid.uuid4().hex[:8]
                if entry_type == "CF":
                    new_worker = create_worker_row(wid, name, total_value, "", "", "", note_text, "CF")
                else:
                    fee = compute_fee(total_value, due_custom_val if due_custom_val > 0 else None)
                    remaining = (total_value / 2) - withdrawn_val - fee
                    new_worker = create_worker_row(wid, name, total_value, fee, withdrawn_val, remaining, note_text)
                
                st.session_state.workers.append(new_worker)
                st.sidebar.success(f"Added {name} successfully!")
                st.rerun()

        st.divider()
        st.header("⚙️ Settings")
        st.session_state.report_date = st.date_input("Report Date", value=st.session_state.report_date)

        if st.button("Reset All Workers", use_container_width=True):
            if st.session_state.workers:
                st.session_state.workers = []
                st.success("All workers have been cleared.")
                st.rerun()
            else:
                st.info("The list is already empty.")

# -----------------------------
# UI: Main Page
# -----------------------------
def show_main_content():
    """Render the main page content (table, metrics, actions)."""
    if not st.session_state.workers:
        st.info("No workers added yet. Use the sidebar to add a new entry.")
        return

    df_internal = pd.DataFrame(st.session_state.workers)
    df_display = df_internal.copy()
    for col in ["Total", "Due", "Withdrawn", "Remaining"]:
        df_display[col] = pd.to_numeric(df_display[col], errors='coerce').fillna(0).apply(clean_number)

    st.subheader("Workers Overview")
    st.caption(f"Date: {st.session_state.report_date.strftime('%Y-%m-%d')}")
    st.dataframe(df_display[["Worker", "Total", "Due", "Withdrawn", "Remaining", "Note"]], use_container_width=True, hide_index=True)

    # --- Actions Expander ---
    with st.expander("Actions"):
        # Create a unique label for each worker to use in selectbox
        worker_options = {f"{w['Worker']} (Total: {w['Total']}) - ID: {w['ID'][:4]}": w['ID'] for w in st.session_state.workers}
        selected_label = st.selectbox("Select a worker to perform an action on", options=worker_options.keys())

        if selected_label:
            st.session_state.action_id = worker_options[selected_label]
            
            col1, col2 = st.columns(2)
            col1.button("Edit Worker", on_click=lambda: st.session_state.update({"show_edit": True}), use_container_width=True)
            col2.button("Delete Worker", on_click=lambda: st.session_state.update({"show_delete": True}), use_container_width=True, type="secondary")

    # --- Financial Summary ---
    st.subheader("Financial Summary")
    numeric_cols = ["Total", "Withdrawn", "Remaining"]
    for col in numeric_cols:
        df_internal[col] = pd.to_numeric(df_internal[col], errors='coerce').fillna(0)
    
    total_sum, withdrawn_sum, remaining_sum = df_internal["Total"].sum(), df_internal["Withdrawn"].sum(), df_internal["Remaining"].sum()
    for_workers = withdrawn_sum + remaining_sum
    for_cleanfoam = total_sum - for_workers

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Total Revenue", f"{total_sum:,.2f}")
    m_col2.metric("For Workers", f"{for_workers:,.2f}")
    m_col3.metric("For CleanFoam", f"{for_cleanfoam:,.2f}")

# --- Dialog Handlers ---
def handle_edit_dialog():
    """Shows the edit dialog if 'show_edit' is true in session state."""
    if st.session_state.get("show_edit"):
        worker_to_edit = next((w for w in st.session_state.workers if w['ID'] == st.session_state.action_id), None)
        if not worker_to_edit: return

        with st.dialog("Edit Worker", dismissed=True):
            with st.form("edit_form"):
                st.write(f"Editing record for: **{worker_to_edit['Worker']}**")
                name = st.text_input("Worker Name", value=worker_to_edit['Worker'])
                total = st.number_input("Total Value", value=float(worker_to_edit['Total']), format="%.2f")
                withdrawn = st.number_input("Withdrawn Value", value=float(worker_to_edit['Withdrawn']), format="%.2f")
                note = st.text_input("Note", value=worker_to_edit['Note'])
                
                if st.form_submit_button("Save Changes", type="primary"):
                    for i, worker in enumerate(st.session_state.workers):
                        if worker['ID'] == st.session_state.action_id:
                            worker['Worker'], worker['Total'], worker['Withdrawn'], worker['Note'] = name, total, withdrawn, note
                            if worker['EntryType'] == 'Standard':
                                fee = compute_fee(total, None)
                                worker['Due'] = fee
                                worker['Remaining'] = (total / 2) - withdrawn - fee
                            break
                    st.session_state.show_edit = False
                    st.rerun()
        # This ensures the dialog doesn't reappear on its own
        if "show_edit" in st.session_state:
            del st.session_state["show_edit"]

def handle_delete_dialog():
    """Shows the delete confirmation dialog if 'show_delete' is true."""
    if st.session_state.get("show_delete"):
        worker_to_delete = next((w for w in st.session_state.workers if w['ID'] == st.session_state.action_id), None)
        if not worker_to_delete: return

        with st.dialog("Confirm Deletion", dismissed=True):
            st.warning(f"Are you sure you want to delete the record for **{worker_to_delete['Worker']}**?")
            c1, c2 = st.columns(2)
            if c1.button("Yes, Delete", type="primary"):
                st.session_state.workers = [w for w in st.session_state.workers if w['ID'] != st.session_state.action_id]
                st.session_state.show_delete = False
                st.rerun()
            if c2.button("Cancel"):
                st.session_state.show_delete = False
                st.rerun()
        if "show_delete" in st.session_state:
            del st.session_state["show_delete"]

# -----------------------------
# Main App Logic
# -----------------------------
def main():
    initialize_session_state()
    show_sidebar()
    show_main_content()
    handle_edit_dialog()
    handle_delete_dialog()

if __name__ == "__main__":
    main()
