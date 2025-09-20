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
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.title("✨ CleanFoam Pro")

# -----------------------------
# Session State Management
# -----------------------------
def initialize_session_state():
    """Initialize session state variables if they don't exist."""
    if "workers" not in st.session_state:
        st.session_state.workers: list[dict] = []
    if "report_date" not in st.session_state:
        st.session_state.report_date = date.today()
    if "theme" not in st.session_state:
        st.session_state.theme = "Light"

# -----------------------------
# Helper Functions
# -----------------------------
def clean_number(n):
    """Render integers without .0 and handle non-numeric types gracefully."""
    if isinstance(n, (int, float)):
        return int(n) if float(n).is_integer() else f"{n:.2f}"
    return n

def compute_fee(total_value: float, custom_due: float | None) -> float:
    """
    Calculate the fee based on business rules.
    Rules are now stored in a dictionary for easier maintenance.
    """
    if custom_due is not None and custom_due > 0:
        return custom_due

    # Rule mapping: (total_value_check, fee)
    rules = {
        80.0: 20.0,
        90.0: 20.0,
        95.0: 22.5,
        100.0: 25.0,
        105.0: 27.5,
        110.0: 25.0,
    }
    
    # Check for exact matches in rules
    fee = rules.get(total_value)
    if fee is not None:
        return fee

    # Fallback rules
    if int(total_value) % 10 == 5:
        return 32.5

    return 30.0

def create_worker_row(worker_id, name, total, due, withdrawn, remaining, note=""):
    """Factory for creating a worker data dictionary."""
    return {
        "ID": worker_id,
        "Worker": name,
        "Total": total,
        "Due": due,
        "Withdrawn": withdrawn,
        "Remaining": remaining,
        "Note": note,
    }

# -----------------------------
# UI: Sidebar Inputs
# -----------------------------
def show_sidebar_inputs():
    """Render all input widgets in the sidebar."""
    with st.sidebar:
        st.header("📝 Add New Entry")
        
        name = st.text_input("Worker Name", help="Enter the name of the worker.")
        total_value = st.number_input("Total Value", min_value=0.0, step=0.5, format="%.2f")
        withdrawn_val = st.number_input("Withdrawn Value", min_value=0.0, step=0.5, format="%.2f")
        
        entry_type = st.radio("Entry Type", ("Standard", "CF"), horizontal=True, index=0)
        
        with st.expander("Advanced Options"):
            due_custom_val = st.number_input("Custom Due (Optional)", min_value=0.0, step=0.5, format="%.2f")
            note_text = st.text_input("Note (Optional)", help="Add any relevant notes.")

        add_clicked = st.button("➕ Add Worker", type="primary", use_container_width=True)

        st.divider()
        st.header("⚙️ Settings")
        st.session_state.report_date = st.date_input("Report Date", value=st.session_state.report_date)

        if st.button("🗑️ Reset All Workers", use_container_width=True):
            if st.session_state.workers:
                st.session_state.workers = []
                st.success("All workers have been cleared.")
                st.rerun()
            else:
                st.info("The list is already empty.")

    return name, total_value, withdrawn_val, entry_type, due_custom_val, note_text, add_clicked

# -----------------------------
# UI: Main Page Display
# -----------------------------
def show_main_content():
    """Render the main page content (table, metrics, actions)."""
    if not st.session_state.workers:
        st.info("No workers added yet. Use the sidebar to add a new entry.")
        return

    df_internal = pd.DataFrame(st.session_state.workers)
    
    # Ensure numeric columns are treated as numbers, coercing errors
    for col in ["Total", "Due", "Withdrawn", "Remaining"]:
        df_internal[col] = pd.to_numeric(df_internal[col], errors='coerce').fillna(0)

    # Create a display version with clean numbers and without the ID
    df_display = df_internal.copy()
    for col in ["Total", "Due", "Withdrawn", "Remaining"]:
        df_display[col] = df_display[col].apply(clean_number)
    
    st.subheader("Workers Overview")
    st.caption(f"Date: {st.session_state.report_date.strftime('%Y-%m-%d')}")
    
    st.dataframe(
        df_display[["Worker", "Total", "Due", "Withdrawn", "Remaining", "Note"]],
        use_container_width=True,
        hide_index=True,
    )

    # --- Metrics ---
    st.subheader("Financial Summary")
    total_sum = df_internal["Total"].sum()
    withdrawn_sum = df_internal["Withdrawn"].sum()
    remaining_sum = df_internal["Remaining"].sum()
    
    for_workers = withdrawn_sum + remaining_sum
    for_cleanfoam = total_sum - for_workers

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Revenue", f"{total_sum:,.2f}")
    col2.metric("👥 For Workers", f"{for_workers:,.2f}")
    col3.metric("🏢 For CleanFoam", f"{for_cleanfoam:,.2f}")

    # --- Actions ---
    with st.expander("⚠️ Actions"):
        # Delete worker
        st.markdown("#### Delete a Worker")
        
        # Create unique labels for workers with the same name
        name_counts = {}
        id_map = {}
        labels = []
        for _, row in df_internal.iterrows():
            name = row["Worker"]
            count = name_counts.get(name, 0) + 1
            name_counts[name] = count
            label = f"{name} (Total: {row['Total']})" + (f" #{count}" if count > 1 else "")
            labels.append(label)
            id_map[label] = row["ID"]

        selected_label = st.selectbox("Select worker to delete", options=labels, index=None, placeholder="Choose a worker...")
        
        if st.button("❌ Delete Selected Worker", type="secondary", disabled=(not selected_label)):
            worker_id_to_delete = id_map[selected_label]
            st.session_state.workers = [w for w in st.session_state.workers if w["ID"] != worker_id_to_delete]
            st.success(f"Deleted: {selected_label}")
            st.rerun()

        # Download CSV
        st.markdown("#### Download Report")
        csv_data = df_display[["Worker", "Total", "Due", "Withdrawn", "Remaining", "Note"]].to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download as CSV",
            data=csv_data,
            file_name=f"cleanfoam_report_{st.session_state.report_date.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

# -----------------------------
# Main App Logic
# -----------------------------
def main():
    initialize_session_state()
    
    name, total_value, withdrawn_val, entry_type, due_custom_val, note_text, add_clicked = show_sidebar_inputs()

    if add_clicked:
        if not name:
            st.sidebar.error("Worker name is required.")
        elif total_value <= 0:
            st.sidebar.error("Total value must be greater than 0.")
        else:
            wid = uuid.uuid4().hex[:8]
            due_custom = None if due_custom_val == 0.0 else due_custom_val
            
            if entry_type == "CF":
                new_worker = create_worker_row(wid, name, total_value, "", "", "", note_text)
            else:
                fee = compute_fee(total_value, due_custom)
                half_value = total_value / 2
                after_withdraw = half_value - withdrawn_val
                remaining = after_withdraw - fee
                new_worker = create_worker_row(wid, name, total_value, fee, withdrawn_val, remaining, note_text)
            
            st.session_state.workers.append(new_worker)
            st.sidebar.success(f"Added {name} successfully!")
            st.rerun()

    show_main_content()

if __name__ == "__main__":
    main()
