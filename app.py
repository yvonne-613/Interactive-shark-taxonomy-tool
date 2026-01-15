import streamlit as st
import pandas as pd
from graphviz import Digraph
import json
from pathlib import Path
import base64

# =========================================================
# SECURE PASSWORD PROTECTION
# =========================================================
def check_password():
    def password_entered():
        # Pulls the password from your hidden secrets.toml file
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Access Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Access Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    return True

if not check_password():
    st.stop()

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="Interactive Shark Phylogeny", layout="wide")

DATA_FILE = "Shark_Taxonomy_Final.xlsx"
PRESET_DIR = Path("presets")
PRESET_DIR.mkdir(exist_ok=True)

LEVELS = ["Class", "Subclass", "Order", "Family", "Genus", "Species"]

LEVEL_COLORS = {
    "Class":    "#f6c1cc",
    "Subclass": "#f8d7b0",
    "Order":    "#fff3b0",
    "Family":   "#ccebdc",
    "Genus":    "#cdd9f2",
    "Species":  "#e6c9ef",
}

# =========================================================
# LOAD DATA
# =========================================================
@st.cache_data
def load_data():
    df = pd.read_excel(DATA_FILE)
    df.columns = df.columns.str.strip()

    missing = set(LEVELS) - set(df.columns)
    if missing:
        st.error(f"Missing required columns: {missing}")
        st.stop()

    for c in LEVELS:
        df[c] = df[c].astype(str).str.strip()

    df["Full_Species"] = df["Genus"] + " " + df["Species"]
    return df

df = load_data()

# =========================================================
# SESSION STATE INITIALIZATION
# =========================================================
for lvl in LEVELS:
    st.session_state.setdefault(f"sel_{lvl.lower()}", [])
    st.session_state.setdefault(f"all_{lvl.lower()}", False)

st.session_state.setdefault("active_levels", LEVELS.copy())
st.session_state.setdefault("chart_title", "Shark Phylogeny")
st.session_state.setdefault("render_requested", False)
st.session_state.setdefault("tree_valid", False)
st.session_state.setdefault("pending_preset", None)
st.session_state.setdefault("highlighted_species", [])

def invalidate_tree():
    st.session_state.tree_valid = False
    st.session_state.render_requested = False

def reset_all_filters_callback():
    for lvl in LEVELS:
        st.session_state[f"sel_{lvl.lower()}"] = []
        st.session_state[f"all_{lvl.lower()}"] = False
    st.session_state["highlighted_species"] = []
    invalidate_tree()

# =========================================================
# APPLY PENDING PRESET (SAFE LOAD)
# =========================================================
if st.session_state.pending_preset is not None:
    preset = st.session_state.pending_preset

    st.session_state.chart_title = preset.get("chart_title", "Shark Phylogeny")
    st.session_state.active_levels = preset.get("active_levels", LEVELS.copy())

    for lvl in LEVELS:
        st.session_state[f"sel_{lvl.lower()}"] = preset.get(f"sel_{lvl.lower()}", [])
        st.session_state[f"all_{lvl.lower()}"] = preset.get(f"all_{lvl.lower()}", False)

    st.session_state.tree_valid = False
    st.session_state.render_requested = False
    st.session_state.pending_preset = None

# =========================================================
# FILTER LOGIC
# =========================================================
def apply_filters(df):
    # We start with the full dataframe. 
    # Instead of filtering out rows, we will just use the selections 
    # to guide the tree builder later.
    dff = df.copy()
    
    # Only filter by the TOP-MOST selection to keep the 'Base' of the tree correct.
    # For example, if you pick a Class, we only show that Class.
    for lvl in LEVELS:
        sel = st.session_state[f"sel_{lvl.lower()}"]
        if sel:
            if lvl == "Species":
                return dff[dff["Full_Species"].isin(sel)]
            else:
                return dff[dff[lvl].isin(sel)]
    return dff




# =========================================================
# FILTER UI
# =========================================================
st.title("🦈 Interactive Shark Taxonomy 🦈")

working_df = df.copy()
cols = st.columns(len(LEVELS))

for i, lvl in enumerate(LEVELS):
    with cols[i]:
        opts = (
            sorted(working_df["Full_Species"].unique())
            if lvl == "Species"
            else sorted(working_df[lvl].unique())
        )

        st.checkbox("Select all available", key=f"all_{lvl.lower()}", on_change=invalidate_tree)

        if st.session_state[f"all_{lvl.lower()}"]:
            st.session_state[f"sel_{lvl.lower()}"] = opts

        st.multiselect(f"{lvl} search", opts, key=f"sel_{lvl.lower()}", on_change=invalidate_tree)

        sel = st.session_state[f"sel_{lvl.lower()}"]
        if sel:
            working_df = working_df[
                working_df["Full_Species"].isin(sel)
                if lvl == "Species"
                else working_df[lvl].isin(sel)
            ]
# =========================================================
# SIDEBAR (PRESETS + COPYRIGHT)
# =========================================================
with st.sidebar:
    st.header("Tree Customization")

    st.text_input("Chart Title", key="chart_title", on_change=invalidate_tree)

    # --- ADD THE HIGHLIGHT TOOL HERE ---
    st.divider()
    st.subheader("🔦 Highlight Species")
    
    # FIX: We use the 'working_df' which has already been narrowed down 
    # by your Order/Family/Genus selections in the main UI
    available_species = sorted(working_df["Full_Species"].unique())
    
    st.multiselect(
        "Select species to highlight",
        options=available_species,
        key="highlighted_species",
        on_change=invalidate_tree,
        help="Only species currently visible in the tree can be highlighted."
    )

    st.divider()
    st.subheader("💾 Saved Views")

    presets = {p.stem: p for p in PRESET_DIR.glob("*.json")}
    choice = st.selectbox("Select preset", [""] + list(presets.keys()))

    c1, c2 = st.columns(2)

    if c1.button("📂 Load") and choice:
        with open(presets[choice]) as f:
            st.session_state.pending_preset = json.load(f)
        st.rerun()

    if c2.button("🗑️ Delete") and choice:
        presets[choice].unlink()
        st.rerun()

    name = st.text_input("Save current as")
    if st.button("💾 Save Preset") and name:
        data = {
            "chart_title": st.session_state.chart_title,
            "active_levels": st.session_state.active_levels,
        }
        for lvl in LEVELS:
            data[f"sel_{lvl.lower()}"] = st.session_state[f"sel_{lvl.lower()}"]
            data[f"all_{lvl.lower()}"] = st.session_state[f"all_{lvl.lower()}"]

        with open(PRESET_DIR / f"{name}.json", "w") as f:
            json.dump(data, f, indent=2)

        st.success("Preset saved")

    st.divider()
    st.markdown(
        "© 2026 Interactive Shark Phylogeny Tool  \n"
        "Created by **Yvonne de Rijk**. All rights reserved."
    )

# =========================================================
# RESET FILTERS
# =========================================================
# The 'on_click' triggers the function BEFORE the widgets are drawn
st.button("🔄 Reset all filters", on_click=reset_all_filters_callback)


# =========================================================
# ACTIVE LEVELS SELECTOR
# =========================================================
st.divider()
active = st.multiselect(
    "Taxonomic levels to show",
    LEVELS,
    default=st.session_state.active_levels,
    on_change=invalidate_tree
)
st.session_state.active_levels = active

idx = [LEVELS.index(l) for l in active]
if idx and idx != list(range(min(idx), max(idx) + 1)):
    st.error("Taxonomic levels must be contiguous.")
    st.stop()

# =========================================================
# TREE CONSTRUCTION
# =========================================================
def build_horizontal_taxonomic_tree(df, active_levels, chart_title):
    dot = Digraph(graph_attr={
        "rankdir": "LR", "nodesep": "1.0", "ranksep": "3.0",
        "splines": "ortho", "fontsize": "40", "label": chart_title,
        "fontname": "Arial-Bold", "labelloc": "t"
    })


    drawn_nodes = set()

    def add_branch(current_df, level_idx):
        if level_idx >= len(active_levels):
            return

        lvl = active_levels[level_idx]
        next_lvl = active_levels[level_idx + 1] if level_idx + 1 < len(active_levels) else None
        
        items = current_df[lvl].unique()

        for item in items:
            node_id = f"{lvl}_{item}"
            
            # --- SHOW FULL SCIENTIFIC NAME IN ITALICS ---
            if lvl == "Species":
                # Find the full name "Genus species" from the dataframe
                row = current_df[current_df["Species"] == item].iloc[0]
                full_name = row["Full_Species"]
                # Wrap in HTML-like tags for italics
                label = f"<<I>{full_name}</I>>"
            else:
                label = item 

            if node_id not in drawn_nodes:
                # Class color remains pastel red as per your settings
                f_color = LEVEL_COLORS.get(lvl, "#FFFFFF")
                e_color = "black"
                p_width = "1"

                # Highlight Logic using Full_Species
                if lvl == "Species":
                    row = current_df[current_df["Species"] == item].iloc[0]
                    if row["Full_Species"] in st.session_state.highlighted_species:
                        f_color = "#FFD1DC"  # Pastel Pink
                        e_color = "#FF69B4"  # Hot Pink
                        p_width = "3"

                dot.node(node_id, label, style="filled", fillcolor=f_color, 
                         color=e_color, penwidth=p_width, shape="box")
                drawn_nodes.add(node_id)

            if next_lvl:
                next_sel = st.session_state.get(f"sel_{next_lvl.lower()}", [])
                
                if not next_sel:
                    child_df = current_df[current_df[lvl] == item]
                    for next_item in child_df[next_lvl].unique():
                        next_id = f"{next_lvl}_{next_item}"
                        dot.edge(node_id, next_id)
                    add_branch(child_df, level_idx + 1)
                else:
                    # Filter for next level: if next is Species, match against Full_Species
                    if next_lvl == "Species":
                        child_df = current_df[(current_df[lvl] == item) & (current_df["Full_Species"].isin(next_sel))]
                    else:
                        child_df = current_df[(current_df[lvl] == item) & (current_df[next_lvl].isin(next_sel))]
                    
                    if not child_df.empty:
                        for next_item in child_df[next_lvl].unique():
                            next_id = f"{next_lvl}_{next_item}"
                            dot.edge(node_id, next_id)
                        add_branch(child_df, level_idx + 1)

    add_branch(df, 0)


    return dot


# =========================================================
# DOWNLOAD HELPERS (PRETTY BUTTON VERSION)
# =========================================================
def get_download_button(dot, filename, format_type, label):
    img = dot.pipe(format=format_type)
    b64 = base64.b64encode(img).decode()
    
    button_style = f"""
        <style>
        .download-btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background-color: #ff4b4b; /* Streamlit Red */
            color: white !important;
            padding: 10px 20px;
            text-decoration: none !important;
            border-radius: 8px;
            font-weight: bold;
            border: none;
            transition: 0.3s;
            width: 100%;
            text-align: center;
            margin-bottom: 10px;
        }}
        .download-btn:hover {{
            background-color: #ff7676;
            text-decoration: none !important;
            color: white !important;
        }}
        </style>
        <a class="download-btn" href="data:file/{format_type};base64,{b64}" download="{filename}">
            {label}
        </a>
    """
    return button_style

# =========================================================
# GENERATE TREE
# =========================================================
if st.button("🚀 Generate Scientific Tree", type="primary"):
    st.session_state.render_requested = True
    st.session_state.tree_valid = True

# =========================================================
# THE DIAGNOSTIC POP-UP FUNCTION
# =========================================================
def count_visible_species(df, active_levels):
    # This mimics the 'add_branch' logic to count how many species nodes 
    # will actually be created after pruning.
    
    # If "Species" isn't even in the active levels, the count is effectively 0 species boxes
    if "Species" not in active_levels:
        return 0

    # We reuse the logic: if a level has no selections, it's "Full Mode"
    # If it has selections, it's "Selective Mode"
    
    current_df = df.copy()
    for lvl in active_levels:
        if lvl == "Species":
            break # We've reached the end
            
        next_lvl = active_levels[active_levels.index(lvl) + 1]
        sel = st.session_state.get(f"sel_{next_lvl.lower()}", [])
        
        if sel:
            # Prune the dataframe to only include selected children
            current_df = current_df[current_df[next_lvl].isin(sel)]
            
    return len(current_df)
@st.dialog("⚠️ Massive Tree Warning")
def show_large_tree_warning(total_species, unfiltered_levels):
    st.write(f"This selection contains **{total_species}** species.")
    
    if unfiltered_levels:
        levels_str = ", ".join([f"**{l}**" for l in unfiltered_levels])
        st.info(f"👉 **Possible cause:** You haven't selected specific items for: {levels_str}. "
                "The app is currently including *every* group within those levels.")
    
    st.write("Building this tree might be slow or difficult to read. What would you like to do?")
    
    col_a, col_b = st.columns(2)
    if col_a.button("✅ Build anyway", use_container_width=True):
        st.session_state.confirmed_large_tree = True
        st.rerun()
    if col_b.button("🔍 Filter more", use_container_width=True):
        st.session_state.render_requested = False
        st.rerun()

# =========================================================
# RENDER TREE BLOCK
# =========================================================
if st.session_state.render_requested and st.session_state.tree_valid:
    final_df = apply_filters(df)
    
    if not final_df.empty:
        total_visible = count_visible_species(final_df, st.session_state.active_levels)
        if total_visible > 50 and not st.session_state.get("confirmed_large_tree"):
            show_large_tree_warning(total_visible, [lvl for lvl in st.session_state.active_levels if not st.session_state.get(f"sel_{lvl.lower()}")])
            st.stop()

        dot = build_horizontal_taxonomic_tree(
            final_df,
            st.session_state.active_levels,
            st.session_state.chart_title
        )
        
        # Display the Tree
        st.graphviz_chart(dot, use_container_width=True)
        
        # --- ADDED EXPORT BUTTONS ---
        st.divider()
        st.subheader("📥 Export Current Tree")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(get_download_button(dot, "shark_tree.png", "png", "🖼️ Download as PNG"), unsafe_allow_html=True)
        with col2:
            st.markdown(get_download_button(dot, "shark_tree.svg", "svg", "🌐 Download as SVG (Vector)"), unsafe_allow_html=True)
        
        st.session_state.confirmed_large_tree = False


