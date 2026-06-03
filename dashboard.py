"""
Table Allocation Optimizer - Web Dashboard

A user-friendly interface for the table allocation system.
Run with: streamlit run dashboard.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tableopt.models import FloorState, Party, PartyType, Table, TableStatus
from tableopt.offline import fit_distributions
from tableopt.optimizer import ScoringConfig, recommend_assignment
from tableopt.priors import PriorDistributions

# Page config
st.set_page_config(
    page_title="Table Allocation Optimizer",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
    <style>
    .big-font {
        font-size:20px !important;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .stAlert {
        margin-top: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state
if "priors" not in st.session_state:
    st.session_state.priors = None
if "floor_state" not in st.session_state:
    st.session_state.floor_state = None
if "config" not in st.session_state:
    st.session_state.config = ScoringConfig()


def main():
    st.title("🍽️ Table Allocation Optimizer")
    st.markdown("*Maximize turnover with data-driven seating recommendations*")

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["🏠 Home", "📊 Train Model", "🎯 Get Recommendations", "⚙️ Settings", "📈 Analytics"],
    )

    if page == "🏠 Home":
        show_home()
    elif page == "📊 Train Model":
        show_train_model()
    elif page == "🎯 Get Recommendations":
        show_recommendations()
    elif page == "⚙️ Settings":
        show_settings()
    elif page == "📈 Analytics":
        show_analytics()


def show_home():
    st.header("Welcome to the Table Allocation Optimizer")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📊 Step 1: Train")
        st.markdown("Upload your historical data to train the model")
        if st.button("Go to Training →", key="home_train"):
            st.session_state.page = "📊 Train Model"
            st.rerun()

    with col2:
        st.markdown("### 🎯 Step 2: Recommend")
        st.markdown("Get real-time seating recommendations")
        if st.button("Get Recommendations →", key="home_rec"):
            st.session_state.page = "🎯 Get Recommendations"
            st.rerun()

    with col3:
        st.markdown("### ⚙️ Step 3: Configure")
        st.markdown("Fine-tune scoring weights")
        if st.button("Open Settings →", key="home_settings"):
            st.session_state.page = "⚙️ Settings"
            st.rerun()

    st.markdown("---")

    # Status
    st.subheader("System Status")
    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.priors:
            st.success("✅ Model Trained")
            st.caption(
                f"Trained on data from {st.session_state.priors.data_range.start_date} "
                f"to {st.session_state.priors.data_range.end_date}"
            )
        else:
            st.warning("⚠️ Model Not Trained")
            st.caption("Upload historical data to train the model")

    with col2:
        if st.session_state.floor_state:
            st.info("📍 Floor State Loaded")
            st.caption(f"{len(st.session_state.floor_state.tables)} tables configured")
        else:
            st.info("📍 No Floor State")
            st.caption("Load or create floor state for recommendations")

    # Quick start guide
    with st.expander("📖 Quick Start Guide"):
        st.markdown(
            """
        1. **Train the Model**: Upload your historical CSV data (reservations + walk-ins)
        2. **Load Floor State**: Upload or create your current restaurant floor layout
        3. **Get Recommendations**: Input party size and get optimal table suggestions
        4. **Adjust Settings**: Fine-tune weights based on your preferences
        """
        )


def show_train_model():
    st.header("📊 Train the Model")
    st.markdown("Upload historical data to learn patterns about your restaurant")

    # File upload
    uploaded_file = st.file_uploader(
        "Upload Historical CSV", type=["csv"], help="CSV with columns: date, arrival_time, party_size, source, table_id, dwell_minutes, no_show"
    )

    if uploaded_file is not None:
        try:
            # Preview data
            df = pd.read_csv(uploaded_file)

            st.subheader("Data Preview")
            st.dataframe(df.head(10), use_container_width=True)

            # Data stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Rows", len(df))
            with col2:
                st.metric("Walk-ins", (df["source"] == "walk_in").sum())
            with col3:
                st.metric("Reservations", (df["source"] == "reservation").sum())
            with col4:
                st.metric("Date Range", f"{df['date'].nunique()} days")

            # Train button
            if st.button("🚀 Train Model", type="primary"):
                with st.spinner("Training model... This may take a moment."):
                    # Save to temp file
                    temp_path = Path("temp_history.csv")
                    df.to_csv(temp_path, index=False)

                    # Fit distributions
                    priors = fit_distributions(str(temp_path), output_path=None)
                    st.session_state.priors = priors

                    # Clean up
                    temp_path.unlink()

                st.success("✅ Model trained successfully!")

                # Show training results
                st.subheader("Training Results")

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Walk-in Patterns**")
                    st.metric("Time Slots Analyzed", len(priors.walk_in_pmf))
                    st.metric("Avg Walk-ins/Hour", f"{sum(priors.walk_in_rate.values()) / max(len(priors.walk_in_rate), 1):.1f}")

                with col2:
                    st.markdown("**Dwell Time Models**")
                    st.metric("Party Size Bands", len(priors.dwell_time))
                    st.metric("No-show Rate", f"{priors.no_show_rate.overall:.1%}")

                # Save priors
                priors_path = Path("artifacts/dashboard_priors.json")
                priors_path.parent.mkdir(exist_ok=True)
                with open(priors_path, "w") as f:
                    json.dump(priors.model_dump(mode="json"), f, indent=2, default=str)

                st.info(f"💾 Priors saved to `{priors_path}`")

        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.caption("Make sure your CSV has all required columns")

    # Load existing priors
    st.markdown("---")
    st.subheader("Or Load Existing Model")

    priors_file = st.file_uploader("Upload Priors JSON", type=["json"])
    if priors_file is not None:
        try:
            priors_data = json.load(priors_file)
            st.session_state.priors = PriorDistributions.model_validate(priors_data)
            st.success("✅ Priors loaded successfully!")
        except Exception as e:
            st.error(f"❌ Error loading priors: {e}")


def show_recommendations():
    st.header("🎯 Get Seating Recommendations")

    if not st.session_state.priors:
        st.warning("⚠️ Please train the model first!")
        if st.button("Go to Training"):
            st.session_state.page = "📊 Train Model"
            st.rerun()
        return

    # Two columns: Floor State and Recommendations
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("🏢 Floor State")

        # Option to upload or use example
        state_option = st.radio("Load floor state from:", ["Upload JSON", "Use Example", "Manual Entry"])

        if state_option == "Upload JSON":
            state_file = st.file_uploader("Upload Floor State JSON", type=["json"])
            if state_file:
                try:
                    state_data = json.load(state_file)
                    st.session_state.floor_state = FloorState.model_validate(state_data)
                    st.success("✅ Floor state loaded!")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

        elif state_option == "Use Example":
            try:
                with open("data/examples/sample_floor_state.json") as f:
                    state_data = json.load(f)
                    st.session_state.floor_state = FloorState.model_validate(state_data)
                st.success("✅ Example floor state loaded!")
            except Exception as e:
                st.error(f"❌ Error loading example: {e}")

        elif state_option == "Manual Entry":
            st.markdown("**Quick Floor Setup**")

            num_tables = st.number_input("Number of tables", 1, 20, 5)

            tables = []
            for i in range(num_tables):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    table_id = st.text_input(f"Table {i+1} ID", f"T{i+1}", key=f"tid_{i}")
                with col_b:
                    capacity = st.number_input(f"Capacity", 2, 12, 4, key=f"cap_{i}")
                with col_c:
                    status = st.selectbox(
                        f"Status", ["free", "occupied", "dirty"], key=f"status_{i}"
                    )

                tables.append(
                    Table(
                        id=table_id,
                        capacity=capacity,
                        status=TableStatus(status),
                    )
                )

            if st.button("Create Floor State"):
                st.session_state.floor_state = FloorState(
                    timestamp=datetime.now(), tables=tables, parties_to_seat=[]
                )
                st.success("✅ Floor state created!")

        # Display current floor state
        if st.session_state.floor_state:
            st.markdown("**Current Tables:**")
            floor_df = pd.DataFrame(
                [
                    {
                        "Table": t.id,
                        "Capacity": t.capacity,
                        "Status": t.status.value,
                    }
                    for t in st.session_state.floor_state.tables
                ]
            )
            st.dataframe(floor_df, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("🎯 Recommendations")

        if st.session_state.floor_state:
            # Party input
            st.markdown("**Party Details:**")
            party_size = st.number_input("Party Size", 1, 20, 4)
            party_type = st.selectbox("Type", ["walk_in", "reservation"])

            if st.button("Get Recommendation", type="primary"):
                party = Party(id="INPUT", size=party_size, type=PartyType(party_type))

                recommendations = recommend_assignment(
                    party,
                    st.session_state.floor_state,
                    st.session_state.priors,
                    st.session_state.config,
                    top_k=3,
                )

                if recommendations and recommendations[0].is_feasible:
                    # Top recommendation
                    top = recommendations[0]

                    st.success(f"**🎯 Recommended: Table {top.table_id}**")
                    st.markdown(f"**Score:** {top.total_score:.2f}")
                    st.markdown(f"*{top.rationale}*")

                    # Score breakdown
                    st.markdown("**Score Breakdown:**")
                    score_df = pd.DataFrame(
                        {
                            "Metric": [
                                "Fit Penalty",
                                "Opportunity Cost",
                                "Reservation Risk",
                            ],
                            "Value": [
                                f"{top.fit_penalty:.3f}",
                                f"{top.opportunity_cost:.3f}",
                                f"{top.reservation_risk:.3f}",
                            ],
                        }
                    )
                    st.dataframe(score_df, use_container_width=True, hide_index=True)

                    # Alternatives
                    if len(recommendations) > 1:
                        st.markdown("---")
                        st.markdown("**Alternative Options:**")
                        for i, rec in enumerate(recommendations[1:], start=2):
                            if rec.is_feasible:
                                with st.expander(
                                    f"{i}. Table {rec.table_id} (Score: {rec.total_score:.2f})"
                                ):
                                    st.markdown(rec.rationale)
                else:
                    st.error("❌ No feasible assignments available")
                    if recommendations:
                        st.caption(recommendations[0].rationale)
        else:
            st.info("👈 Load floor state first")


def show_settings():
    st.header("⚙️ Settings")
    st.markdown("Configure scoring weights and constraints")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Scoring Weights")

        horizon = st.slider(
            "Horizon (minutes)",
            30,
            180,
            st.session_state.config.horizon_minutes,
            15,
            help="How far ahead to consider future demand",
        )

        fit_weight = st.slider(
            "Fit Penalty Weight",
            0.0,
            2.0,
            st.session_state.config.fit_penalty_weight,
            0.1,
            help="Higher = care more about wasted seats",
        )

        opp_weight = st.slider(
            "Opportunity Cost Weight",
            0.0,
            2.0,
            st.session_state.config.opportunity_cost_weight,
            0.1,
            help="Higher = care more about future walk-ins",
        )

    with col2:
        st.subheader("Constraints")

        hard_block = st.checkbox(
            "Hard Reservation Block",
            st.session_state.config.reservation_hard_block,
            help="Never block confirmed reservations",
        )

        combine_penalty = st.slider(
            "Table Combine Penalty",
            0.0,
            1.0,
            st.session_state.config.combine_penalty_weight,
            0.1,
            help="Penalty for combining tables",
        )

    # Apply settings
    if st.button("💾 Save Settings", type="primary"):
        st.session_state.config = ScoringConfig(
            horizon_minutes=horizon,
            fit_penalty_weight=fit_weight,
            opportunity_cost_weight=opp_weight,
            reservation_hard_block=hard_block,
            combine_penalty_weight=combine_penalty,
        )
        st.success("✅ Settings saved!")

    # Export config
    st.markdown("---")
    if st.button("📥 Export Configuration"):
        config_dict = {
            "horizon_minutes": st.session_state.config.horizon_minutes,
            "opportunity_cost_weight": st.session_state.config.opportunity_cost_weight,
            "fit_penalty_weight": st.session_state.config.fit_penalty_weight,
            "reservation_hard_block": st.session_state.config.reservation_hard_block,
            "combine_penalty_weight": st.session_state.config.combine_penalty_weight,
        }
        st.download_button(
            "Download config.json",
            json.dumps(config_dict, indent=2),
            "config.json",
            "application/json",
        )


def show_analytics():
    st.header("📈 Analytics")

    if not st.session_state.priors:
        st.warning("⚠️ Please train the model first to see analytics!")
        return

    priors = st.session_state.priors

    # Walk-in patterns
    st.subheader("Walk-in Patterns")

    if priors.walk_in_pmf:
        # Parse walk-in data
        walk_in_data = []
        for slot, pmf in priors.walk_in_pmf.items():
            day, hour = slot.split("_")
            day_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][int(day)]
            for size, prob in pmf.items():
                walk_in_data.append(
                    {
                        "Day": day_name,
                        "Hour": int(hour),
                        "Party Size": int(size),
                        "Probability": prob,
                    }
                )

        df = pd.DataFrame(walk_in_data)

        # Heatmap data
        if not df.empty:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Average Walk-in Rate by Hour**")
                rate_data = []
                for slot, rate in priors.walk_in_rate.items():
                    day, hour = slot.split("_")
                    rate_data.append({"Hour": int(hour), "Rate": rate})

                if rate_data:
                    rate_df = pd.DataFrame(rate_data).groupby("Hour").mean().reset_index()
                    st.bar_chart(rate_df.set_index("Hour"))

            with col2:
                st.markdown("**Party Size Distribution**")
                size_prob = df.groupby("Party Size")["Probability"].mean().reset_index()
                st.bar_chart(size_prob.set_index("Party Size"))

    # Dwell time
    st.markdown("---")
    st.subheader("Dwell Time Analysis")

    if priors.dwell_time:
        dwell_data = []
        for band, params in priors.dwell_time.items():
            dwell_data.append(
                {
                    "Party Size": band,
                    "Avg Dwell (min)": params.mean,
                    "Std Dev": params.std,
                    "Sample Size": params.sample_size,
                }
            )

        dwell_df = pd.DataFrame(dwell_data)
        st.dataframe(dwell_df, use_container_width=True, hide_index=True)

    # No-show rates
    st.markdown("---")
    st.subheader("No-Show Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Overall No-Show Rate", f"{priors.no_show_rate.overall:.1%}")

    with col2:
        if priors.no_show_rate.by_party_size:
            st.markdown("**By Party Size:**")
            for size, rate in priors.no_show_rate.by_party_size.items():
                st.caption(f"Size {size}: {rate:.1%}")


if __name__ == "__main__":
    main()
