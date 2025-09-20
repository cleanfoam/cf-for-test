import sqlite3
import pandas as pd
import streamlit as st
from datetime import date

# -----------------------------
# 1. App Configuration & Constants
# -----------------------------
st.set_page_config(
    page_title="CleanFoam Pro",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.title("CleanFoam Pro")
DB_FILE = "cleanfoam_data.db"

# -----------------------------
# 2. Database Management
# -----------------------------
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(DB_FILE)

def init_db():
    """Initializes the database and creates the 'workers' table if it doesn't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                name TEXT NOT NULL,
                total REAL NOT NULL,
                due REAL,
                withdrawn REAL,
                remaining REAL,
                note TEXT,
                entry_type TEXT NOT NULL
            )
        """)
        conn.commit()

def db_execute(query: str, params: tuple = ()):
    """Executes a write query (INSERT, UPDATE, DELETE)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

def db_fetch_all(query: str, params: tuple = ()) -> pd.DataFrame:
    """Fetches all records for a SELECT query and returns a DataFrame."""
    with get_db_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)

# -----------------------------
# 3. Business Logic & Helper Functions
# -----------------------------
def clean_number(n):
    """Formats a number, showing two decimal places for floats and no decimals for integers."""
    if isinstance(n, (int, float)):
        return int(n) if float(n).is_integer() else f"{n:.2f}"
    return n

def compute_fee(total_value: float, custom_due: float | None) -> float:
    """Calculates the fee based on predefined business rules."""
    if custom_due is not None and custom_due > 0:
        return custom_due
    
    rules = {80.0: 20.0, 90.0: 20.0, 95.0: 22.5, 100.0: 25.0, 105.0: 27.5, 110.0: 25.0}
    fee = rules.get(total_value)
    
    if fee is not None:
        return fee
    if int(total_value) % 10 == 5:
        return 32.5
    return 30.0

def calculate_worker_finances(total: float, withdrawn: float, custom_due: float | None, entry_type: str) -> dict:
    """Calculates financial details for a standard worker entry."""
    if entry_type == "CF":
        return {"due": 0, "withdrawn": 0, "remaining": 0}
    
    fee = compute_fee(total, custom_due)
    remaining = (total / 2) - withdrawn - fee
    return {"due": fee, "withdrawn": withdrawn, "remaining": remaining}

# -----------------------------
# 4. UI Components
# -----------------------------
def show_add_worker_form():
    """Displays the form for adding a new worker entry."""
    st.subheader("Add New Entry")
    with st.form(key="add_worker_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([1.5, 1, 1, 2])
        with c1: name = st.text_input("Worker Name")
        with c2: total_value = st.number_input("Total Value", min_value=0.0, step=0.5, format="%.2f")
        with c3: withdrawn_val = st.number_input("Withdrawn Value", min_value=0.0, step=0.5, format="%.2f")
        with c4: note_text = st.text_input("Note (Optional)")

        c5, c6, c7 = st.columns([1.5, 1, 2])
        with c5: entry_type = st.radio("Entry Type", ("Standard", "CF"), horizontal=True)
        with c6: due_custom_val = st.number_input("Custom Due", min_value=0.0, step=0.5, format="%.2f")
        with c7: add_clicked = st.form_submit_button("Add Worker", type="primary", use_container_width=True)

        if add_clicked:
            if not name:
                st.error("Worker name is required.")
                return
            
            finances = calculate_worker_finances(total_value, withdrawn_val, due_custom_val, entry_type)
            
            db_execute(
                "INSERT INTO workers (report_date, name, total, due, withdrawn, remaining, note, entry_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (st.session_state.report_date.strftime('%Y-%m-%d'), name, total_value, finances['due'], finances['withdrawn'], finances['remaining'], note_text, entry_type)
            )
            st.success(f"Added worker: {name}")
            st.rerun()

def show_financial_summary(df: pd.DataFrame):
    """Displays the key financial metrics."""
    st.subheader("Financial Summary")
    if df.empty:
        st.info("No data available to calculate summary.")
        return

    total_sum = pd.to_numeric(df["total"], errors='coerce').sum()
    withdrawn_sum = pd.to_numeric(df["withdrawn"], errors='coerce').sum()
    remaining_sum = pd.to_numeric(df["remaining"], errors='coerce').sum()
    
    for_workers = withdrawn_sum + remaining_sum
    for_cleanfoam = total_sum - for_workers

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Revenue", f"{total_sum:,.2f}")
    c2.metric("For Workers", f"{for_workers:,.2f}")
    c3.metric("For CleanFoam", f"{for_cleanfoam:,.2f}")

# -----------------------------
# 5. Main Application Logic
# -----------------------------
def main():
    init_db()

    # --- Sidebar for Date and Actions ---
    st.sidebar.header("Settings")
    st.session_state.report_date = st.sidebar.date_input("Report Date", date.today())
    
    # --- Main Page ---
    show_add_worker_form()
    st.divider()

    st.subheader("Workers Overview")
    df = db_fetch_all("SELECT * FROM workers WHERE report_date = ?", (st.session_state.report_date.strftime('%Y-%m-%d'),))

    if df.empty:
        st.info("No workers found for the selected date. Use the form above to add an entry.")
        return

    # --- Data Table with Actions ---
    df['edit'] = False
    df['delete'] = False
    
    column_config = {
        "id": None, "report_date": None, "entry_type": None, # Hide internal columns
        "name": st.column_config.TextColumn("Worker"),
        "total": st.column_config.NumberColumn("Total", format="%.2f"),
        "due": st.column_config.NumberColumn("Due", format="%.2f"),
        "withdrawn": st.column_config.NumberColumn("Withdrawn", format="%.2f"),
        "remaining": st.column_config.NumberColumn("Remaining", format="%.2f"),
        "note": st.column_config.TextColumn("Note"),
        "edit": st.column_config.CheckboxColumn("Edit", default=False),
        "delete": st.column_config.CheckboxColumn("Delete", default=False),
    }
    
    edited_df = st.data_editor(df, hide_index=True, use_container_width=True, column_config=column_config, key="data_editor")

    # --- Handle Edit Action ---
    edit_row = edited_df[edited_df['edit']].iloc[0] if not edited_df[edited_df['edit']].empty else None
    if edit_row is not None:
        with st.dialog("Edit Worker", dismissed=True):
            st.write(f"Editing record for: **{edit_row['name']}**")
            with st.form("edit_form"):
                name = st.text_input("Worker Name", value=edit_row['name'])
                total = st.number_input("Total Value", value=float(edit_row['total']), format="%.2f")
                withdrawn = st.number_input("Withdrawn Value", value=float(edit_row['withdrawn']), format="%.2f")
                note = st.text_input("Note", value=edit_row['note'])
                
                if st.form_submit_button("Save Changes", type="primary"):
                    finances = calculate_worker_finances(total, withdrawn, None, edit_row['entry_type'])
                    db_execute(
                        "UPDATE workers SET name=?, total=?, due=?, withdrawn=?, remaining=?, note=? WHERE id=?",
                        (name, total, finances['due'], finances['withdrawn'], finances['remaining'], note, int(edit_row['id']))
                    )
                    st.success("Worker data updated successfully.")
                    st.rerun()

    # --- Handle Delete Action ---
    delete_row = edited_df[edited_df['delete']].iloc[0] if not edited_df[edited_df['delete']].empty else None
    if delete_row is not None:
        with st.dialog("Confirm Deletion", dismissed=True):
            st.warning(f"Are you sure you want to delete the record for **{delete_row['name']}**?")
            c1, c2 = st.columns(2)
            if c1.button("Yes, Delete", type="primary"):
                db_execute("DELETE FROM workers WHERE id=?", (int(delete_row['id']),))
                st.success(f"Deleted worker: {delete_row['name']}")
                st.rerun()
            if c2.button("Cancel"):
                st.rerun()

    st.divider()
    show_financial_summary(df)

    # --- Download CSV in Sidebar ---
    csv_df = df[['name', 'total', 'due', 'withdrawn', 'remaining', 'note']]
    csv_data = csv_df.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label="Download Report as CSV",
        data=csv_data,
        file_name=f"cleanfoam_report_{st.session_state.report_date.strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

if __name__ == "__main__":
    main()
