import streamlit as st
import pandas as pd
from graphviz import Digraph
import json
from pathlib import Path
import base64

# =========================================================
# PASSWORD PROTECTION
# =========================================================
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Please enter the access password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error.
        st.text_input(
            "Please enter the access password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct.
        return True

if not check_password():
    st.stop()  # Do not run the rest of the app if not authenticated

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
    dff = df.copy()
    for lvl in LEVELS:
        sel = st.session_state[f"sel_{lvl.lower()}"]
        if sel:
            if lvl == "Species":
                dff = dff[dff["Full_Species"].isin(sel)]
            else:
                dff = dff[dff[lvl].isin(sel)]
    return dff

# =========================================================
# SIDEBAR (PRESETS + COPYRIGHT)
# =========================================================
with st.sidebar:
    st.header("Tree Customization")

    st.text_input("Chart Title", key="chart_title", on_change=invalidate_tree)

    # --- ADD THE HIGHLIGHT TOOL HERE ---
    st.divider()
    st.subheader("🔦 Highlight Species")
    
    # We apply current filters to get the list of available species
    current_filtered_df = apply_filters(df)
    available_species = sorted(current_filtered_df["Full_Species"].unique())
    
    st.multiselect(
        "Select species to highlight",
        options=available_species,
        key="highlighted_species",
        on_change=invalidate_tree
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
    dot = Digraph(
        graph_attr={
            "rankdir": "LR",
            "nodesep": "0.7",
            "ranksep": "1.2",
            "fontsize": "30",
            "label": chart_title,
	    "fontname": "Arial",
            "labelloc": "t",
            "labeljust": "c",
        }
    )

    # -----------------------------------------------------
    # Header nodes (one per taxonomic level)
    # -----------------------------------------------------
    for lvl in active_levels:
        dot.node(
            f"header_{lvl}",
            label=lvl,
            shape="plaintext",
            fontsize="16",
            fontname="Arial"
        )

    node_ids = {}

    def node_id(path):
        return "||".join(path)

    # -----------------------------------------------------
    # Create taxon nodes
    # -----------------------------------------------------
    for _, row in df.iterrows():
        path = []
        for lvl in active_levels:
            label = (
                f"{row['Genus']} {row['Species']}"
                if lvl == "Species"
                else row[lvl]
            )
            path.append(label)
            nid = node_id(path)

            if nid not in node_ids:
                node_ids[nid] = lvl
                
                # Default Colors
                fill_color = LEVEL_COLORS[lvl]
                edge_color = "black"
                font_color = "black"
                penwidth = "1"

                # APPLY HIGHLIGHTING (Only for Species level)
                if lvl == "Species" and label in st.session_state.highlighted_species:
                    fill_color = "#FFD1DC"  # Pastel Pink
                    edge_color = "#FF69B4"  # Hot Pink
                    font_color = "#880E4F"  # Very Dark Pink
                    penwidth = "3"         # Makes the Hot Pink edge thicker

                dot.node(
                    nid,
                    label=label,
                    shape="ellipse",
                    style="filled",
                    fillcolor=fill_color,
                    color=edge_color,       # Border color
                    fontcolor=font_color,   # Text color
                    penwidth=penwidth,      # Border thickness
                    fontname="Helvetica",
                    fontsize="12",
                )

    # -----------------------------------------------------
    # Align headers above their respective columns
    # -----------------------------------------------------
    for lvl in active_levels:
        idx = active_levels.index(lvl)

        column_nodes = set()
        for _, row in df.iterrows():
            label_path = []
            for l in active_levels[: idx + 1]:
                label_path.append(
                    f"{row['Genus']} {row['Species']}"
                    if l == "Species"
                    else row[l]
                )
            column_nodes.add(node_id(label_path))

        with dot.subgraph() as s:
            s.attr(rank="same")
            s.node(f"header_{lvl}")
            for n in column_nodes:
                s.node(n)

        for n in column_nodes:
            dot.edge(f"header_{lvl}", n, style="invis")

    # -----------------------------------------------------
    # Create visible hierarchy edges
    # -----------------------------------------------------
    edges = set()
    for _, row in df.iterrows():
        path = []
        for lvl in active_levels:
            label = (
                f"{row['Genus']} {row['Species']}"
                if lvl == "Species"
                else row[lvl]
            )
            path.append(label)

        for i in range(len(path) - 1):
            parent = node_id(path[: i + 1])
            child = node_id(path[: i + 2])
            if (parent, child) not in edges:
                edges.add((parent, child))
                dot.edge(parent, child)

    return dot


# =========================================================
# DOWNLOAD HELPERS
# =========================================================
def get_image_download_link(dot, filename):
    img = dot.pipe(format="png")
    b64 = base64.b64encode(img).decode()
    return f'<a href="data:file/png;base64,{b64}" download="{filename}">🖼️ Download PNG</a>'

def get_svg_download_link(dot, filename):
    svg = dot.pipe(format="svg")
    b64 = base64.b64encode(svg).decode()
    return f'<a href="data:image/svg+xml;base64,{b64}" download="{filename}">🌐 Download SVG</a>'

# =========================================================
# GENERATE TREE
# =========================================================
if st.button("🚀 Generate Scientific Tree", type="primary"):
    st.session_state.render_requested = True
    st.session_state.tree_valid = True

# =========================================================
# RENDER TREE
# =========================================================
if st.session_state.render_requested and st.session_state.tree_valid:
    final_df = apply_filters(df)

    if final_df.empty:
        st.warning("No taxa available.")
    else:
        dot = build_horizontal_taxonomic_tree(
            final_df,
            st.session_state.active_levels,
            st.session_state.chart_title
        )
        st.graphviz_chart(dot)
        st.markdown(get_image_download_link(dot, f"{st.session_state.chart_title}.png"), unsafe_allow_html=True)
        st.markdown(get_svg_download_link(dot, f"{st.session_state.chart_title}.svg"), unsafe_allow_html=True)

