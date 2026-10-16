# =====================================================================
# Creative Pretest Lab: Streamlit in Snowflake data story
# Business question: which of 4 ads should get the launch budget, and for whom?
# AI persona pretest (MiroFish + Snowflake Cortex) checked against real 2017 audience costs
# Repo path: streamlit/creative_pretest_lab.py
# Runs as REPORTER on REPORTING_WH; reads the dbt marts only.
# =====================================================================
import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path

st.set_page_config(page_title="Creative Pretest Lab", layout="wide")
SCHEMA = "ANALYTICS.DBT_GBONTHU"
DATA_DIR = Path(__file__).parent / "data"   # CSV snapshot used outside Snowflake

# Inside Snowflake: read live dbt marts. Anywhere else (e.g. Streamlit Community Cloud): read the CSV snapshot.
try:
    from snowflake.snowpark.context import get_active_session
    session = get_active_session()
except Exception:
    session = None

ADS = {
    "A_free_trial":       ("A: Free Trial",         "Try Stride Studio free for 7 days",                 "#7aa2f7"),
    "B_real_members":     ("B: Real Members",       "50,000 people stopped paying for a gym they never used", "#2ac3de"),
    "C_20_minutes":       ("C: 20 Minutes for You", "The kids are asleep. You have 20 minutes.",         "#e0af68"),
    "D_30_day_challenge": ("D: 30-Day Challenge",   "The 30-Day Reset starts Monday",                    "#9d7cd8"),
}
AD_ORDER = [v[0] for v in ADS.values()]
AD_COLOR = alt.Scale(domain=AD_ORDER, range=[v[2] for v in ADS.values()])
GREY = "#565f89"

# ---------------------------------------------------------------- style
st.markdown(
    """
<style>
.block-container {padding-top: 3.5rem; max-width: 1300px;}
@keyframes fadeUp {from {opacity: 0; transform: translateY(16px);} to {opacity: 1; transform: none;}}
.chapter {animation: fadeUp .6s ease-out both;}
.kicker {font-size: .8rem; letter-spacing: .12em; text-transform: uppercase; opacity: .6;}
.big {font-size: 1.9rem; font-weight: 700; line-height: 1.25; margin: 4px 0 10px;}
.takeaway {border-left: 5px solid #e0af68; background: rgba(224,175,104,.10); border-radius: 10px;
           padding: 14px 18px; font-size: 1.05rem; animation: fadeUp .8s ease-out both; animation-delay: .25s;}
.card {border: 1px solid rgba(127,127,127,.25); border-radius: 12px; padding: 14px 16px; height: 100%;
       animation: fadeUp .6s ease-out both;}
.card .tag {font-weight: 700;} .card .hl {opacity: .8; margin-top: 6px; font-style: italic;}
.stat {font-size: 2.2rem; font-weight: 700;} .statlbl {opacity: .65; font-size: .85rem;}
.limits {border: 1px solid rgba(127,127,127,.35); background: rgba(127,127,127,.06); border-radius: 12px;
         padding: 16px 20px; animation: fadeUp .8s ease-out both; animation-delay: .35s;}
.limits b.t {font-size: 1.05rem;}
.rec {border: 1px solid rgba(127,127,127,.35); background: rgba(127,127,127,.06); border-radius: 12px; padding: 16px 20px;
      animation: fadeUp .7s ease-out both;}
.src {font-size: .75rem; opacity: .55; margin-top: 2px;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- data
def num(df, cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data
def load():
    if session is not None:
        mart = session.sql(f"select * from {SCHEMA}.MART_CREATIVE_PRETEST__SEGMENT_AD").to_pandas()
        rx = session.sql(f"""
            select persona_name, ad_mentioned, intent, sentiment_score, content
            from {SCHEMA}.INT_MIROFISH__REACTIONS_ENRICHED
        """).to_pandas()
    else:
        mart = pd.read_csv(DATA_DIR / "mart_creative_pretest__segment_ad.csv")
        rx = pd.read_csv(DATA_DIR / "reactions_enriched.csv")
        mart.columns, rx.columns = mart.columns.str.upper(), rx.columns.str.upper()
        mart["IS_LOW_SAMPLE"] = mart.IS_LOW_SAMPLE.astype(str).str.lower().eq("true")
    mart = num(mart, ["SIM_REACTIONS", "SIM_WILL_TRY", "SIM_WILL_TRY_RATE", "REAL_COST_PER_CONVERSION"])
    mart["SEGMENT"] = mart.GENDER.map({"F": "Women", "M": "Men"}) + " " + mart.AGE_BAND
    return mart, num(rx, ["SENTIMENT_SCORE"])


mart, rx = load()

by_ad = mart.groupby("AD_NAME", as_index=False)[["SIM_REACTIONS", "SIM_WILL_TRY"]].sum()
by_ad["PCT"] = (by_ad.SIM_WILL_TRY / by_ad.SIM_REACTIONS.where(by_ad.SIM_REACTIONS > 0) * 100).round(0)
by_ad["RELIABLE"] = by_ad.SIM_REACTIONS >= 10
winner = by_ad[by_ad.RELIABLE].sort_values("PCT", ascending=False).iloc[0]

seg = (mart.groupby(["SEGMENT", "GENDER", "AGE_BAND"], as_index=False)
           .agg(R=("SIM_REACTIONS", "sum"), W=("SIM_WILL_TRY", "sum"), COST=("REAL_COST_PER_CONVERSION", "max")))
seg["SIM_PCT"] = (seg.W / seg.R.where(seg.R > 0) * 100).round(0)
cheap, pricey = seg.sort_values("COST").iloc[0], seg.sort_values("COST").iloc[-1]


def takeaway(text):
    st.markdown(f'<div class="takeaway">💡 {text}</div>', unsafe_allow_html=True)


SIM = "Simulated data: MiroFish AI personas, reactions tagged by Snowflake Cortex"
REAL = "Real data: 2017 Facebook ad campaigns (Kaggle, Sales Conversion Optimization)"


def source(*labels):
    st.markdown("".join(f'<div class="src">Source · {l}</div>' for l in labels), unsafe_allow_html=True)


def header(kicker, title):
    st.markdown(f'<div class="chapter"><div class="kicker">{kicker}</div><div class="big">{title}</div></div>',
                unsafe_allow_html=True)


# ---------------------------------------------------------------- navigation
CHAPTERS = ["1 · The problem", "2 · Which ad?", "3 · For whom?", "4 · Reality check", "5 · Decision"]
if "ch" not in st.session_state:
    st.session_state.ch = 0

top_l, top_r = st.columns([2, 3])
top_l.markdown("### Creative Pretest Lab")
choice = top_r.radio("Chapter", CHAPTERS, index=st.session_state.ch, horizontal=True, label_visibility="collapsed")
st.session_state.ch = CHAPTERS.index(choice)
st.divider()
ch = st.session_state.ch

# ================================================================ 1. the problem
if ch == 0:
    header("Scenario", "A fitness app is launching. It has 4 ad ideas and one budget. Which ad, for which audience?")
    cols = st.columns(4)
    for col, (code, (name, headline, color)) in zip(cols, ADS.items()):
        col.markdown(f'<div class="card" style="border-top: 4px solid {color}"><div class="tag">{name}</div>'
                     f'<div class="hl">“{headline}”</div></div>', unsafe_allow_html=True)
    st.write("")
    a, b, c, d = st.columns(4)
    for col, val, lbl in [(a, "48", "AI personas, ages 30–49"), (b, f"{len(rx)}", "reactions analysed by Cortex"),
                          (c, "8", "audience segments"), (d, "$0", "media spend to get here")]:
        col.markdown(f'<div class="chapter"><div class="stat">{val}</div><div class="statlbl">{lbl}</div></div>',
                     unsafe_allow_html=True)
    st.write("")
    takeaway("Testing 4 ads live takes weeks and real money. Instead, we showed all 4 to 48 simulated consumers, "
             "had Snowflake's AI read every reaction, and checked the audiences against real 2017 ad costs.")
    source(SIM, REAL)

# ================================================================ 2. which ad
elif ch == 1:
    header("Question 1", "Which ad makes people want to sign up?")
    left, right = st.columns([3, 2])
    with left:
        chart = by_ad.assign(SHOW=lambda d: d.RELIABLE.map({True: "Enough data", False: "Too few reactions"}))
        bars = alt.Chart(chart).mark_bar(cornerRadiusEnd=6, height=34).encode(
            y=alt.Y("AD_NAME:N", sort=AD_ORDER, title=None, axis=alt.Axis(labelLimit=220)),
            x=alt.X("PCT:Q", title="Would sign up (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.condition("datum.RELIABLE", alt.Color("AD_NAME:N", scale=AD_COLOR, legend=None),
                                alt.value(GREY)),
            tooltip=[alt.Tooltip("AD_NAME", title="Ad"), alt.Tooltip("PCT", title="Would sign up %"),
                     alt.Tooltip("SIM_REACTIONS", title="Reactions"), alt.Tooltip("SHOW", title="Sample")],
        )
        text = alt.Chart(chart).mark_text(align="left", dx=6, color="#94a3b8", fontWeight="bold").encode(
            y=alt.Y("AD_NAME:N", sort=AD_ORDER), x="PCT:Q",
            text=alt.Text("SIM_REACTIONS:Q", format="d"))
        st.altair_chart((bars + text).properties(height=280), use_container_width=True)
        st.caption("Number after each bar = reactions. Grey = too few reactions to trust.")
        source(SIM)
    with right:
        best_q = (rx[(rx.AD_MENTIONED == [k for k, v in ADS.items() if v[0] == winner.AD_NAME][0])
                     & (rx.INTENT == "will_try")].sort_values("SENTIMENT_SCORE", ascending=False).head(1))
        if not best_q.empty:
            qrow = best_q.iloc[0]
            st.markdown(f'<div class="card"><div class="kicker">A persona on {winner.AD_NAME}</div>'
                        f'<div class="hl">“{qrow.CONTENT}”</div><div class="statlbl" style="margin-top:8px">'
                        f'— {qrow.PERSONA_NAME}</div></div>', unsafe_allow_html=True)
    takeaway(f"<b>{winner.AD_NAME}</b> has the strongest signal: {int(winner.PCT)}% of {int(winner.SIM_REACTIONS)} reactions said they'd sign up. "
             "At this sample size, its lead over the next ad is within the margin of error. "
             "A and B barely came up in conversation, so they haven't lost yet. They need a fairer test.")

# ================================================================ 3. for whom
elif ch == 2:
    header("Question 2", "Who should see each ad?")
    pick = st.radio("Ad", AD_ORDER, index=AD_ORDER.index(winner.AD_NAME), horizontal=True,
                    label_visibility="collapsed")
    d = mart[mart.AD_NAME == pick].copy()
    d["PCT"] = (d.SIM_WILL_TRY_RATE * 100).round(0)
    d["OK"] = ~d.IS_LOW_SAMPLE
    color = [v[2] for v in ADS.values() if v[0] == pick][0]
    st.altair_chart(
        alt.Chart(d).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
            x=alt.X("SEGMENT:N", sort=list(seg.SEGMENT), title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("PCT:Q", title="Would sign up (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.condition("datum.OK", alt.value(color), alt.value(GREY)),
            tooltip=["SEGMENT", alt.Tooltip("PCT", title="Would sign up %"),
                     alt.Tooltip("SIM_REACTIONS", title="Reactions")],
        ).properties(height=320),
        use_container_width=True,
    )
    st.caption("Grey = fewer than 5 reactions in that audience.")
    source(SIM)
    ok = d[d.OK].sort_values("PCT", ascending=False)
    if ok.empty:
        takeaway(f"Not enough reactions to pick an audience for <b>{pick}</b> yet. It needs its own test run.")
    else:
        b = ok.iloc[0]
        takeaway(f"For <b>{pick}</b>, the most receptive audience is <b>{b.SEGMENT}</b> "
                 f"({int(b.PCT)}% would sign up, {int(b.SIM_REACTIONS)} reactions).")

# ================================================================ 4. reality check
elif ch == 3:
    header("Question 3", "Do the simulated audiences match real-world behaviour?")
    left, right = st.columns(2)
    with left:
        st.markdown("**Benchmark: real 2017 cost per conversion**")
        st.altair_chart(
            alt.Chart(seg).mark_bar(cornerRadiusEnd=6).encode(
                y=alt.Y("SEGMENT:N", sort="x", title=None),
                x=alt.X("COST:Q", title="$ per conversion (lower is better)"),
                color=alt.Color("GENDER:N", scale=alt.Scale(domain=["F", "M"], range=["#f4b8e4", "#7dcfff"]),
                                legend=None),
                tooltip=["SEGMENT", alt.Tooltip("COST", format="$.2f", title="Cost per conversion")],
            ).properties(height=300),
            use_container_width=True,
        )
        source(REAL)
    with right:
        st.markdown("**Simulated: would sign up (all ads)**")
        st.altair_chart(
            alt.Chart(seg).mark_bar(cornerRadiusEnd=6).encode(
                y=alt.Y("SEGMENT:N", sort=list(seg.sort_values("COST").SEGMENT), title=None),
                x=alt.X("SIM_PCT:Q", title="Would sign up (%)", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("GENDER:N", scale=alt.Scale(domain=["F", "M"], range=["#f4b8e4", "#7dcfff"]),
                                legend=None),
                tooltip=["SEGMENT", alt.Tooltip("SIM_PCT", title="Would sign up %"),
                         alt.Tooltip("R", title="Reactions")],
            ).properties(height=300),
            use_container_width=True,
        )
        source(SIM)
    st.caption("Both charts list audiences in the same order: cheapest real audience at the top.")
    takeaway(f"Real ads were cheapest for <b>{cheap.SEGMENT}</b> (${cheap.COST:.0f}) and most expensive for "
             f"<b>{pricey.SEGMENT}</b> (${pricey.COST:.0f}). The simulation agrees at those extremes "
             f"({int(cheap.SIM_PCT)}% vs {int(pricey.SIM_PCT)}% would sign up), but not everywhere in between.")

# ================================================================ 5. decision
else:
    header("Recommendation", "What to do with the budget")
    best_by_ad = []
    for name in AD_ORDER:
        ok = mart[(mart.AD_NAME == name) & ~mart.IS_LOW_SAMPLE].sort_values("SIM_WILL_TRY_RATE", ascending=False)
        if not ok.empty:
            best_by_ad.append(f"<li><b>{name}</b> → {ok.iloc[0].SEGMENT}</li>")
    st.markdown(
        f"""<div class="rec"><b>Plan</b><ol>
<li>Treat <b>{winner.AD_NAME}</b> as the front-runner and test it live first.</li>
<li>Target each tested ad at its best audience:<ul>{''.join(best_by_ad)}</ul></li>
<li>Re-run the simulation with equal exposure for <b>A</b> and <b>B</b> before ruling them out.</li>
<li>Confirm the top 1–2 ads with a <b>small live A/B test</b> before committing the full budget.</li>
</ol></div>""",
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown(
        """<div class="limits"><b class="t">Limitations: read before acting</b><ul>
<li><b>Small sample.</b> 88 reactions from one partial run, about 10 per audience. Directional only.</li>
<li><b>AI personas are too agreeable.</b> 45% claimed they already use an app they had just seen, and only 1 reaction was negative.
Use results to <b>rank</b> ads, not as real conversion rates.</li>
<li><b>Uneven exposure.</b> The simulation's opening posts mentioned C and D, so A and B were under-tested.</li>
<li><b>The benchmark is 2017 and by audience only.</b> It shows which audiences convert cheaply, not how these four ads perform.</li>
</ul></div>""",
        unsafe_allow_html=True,
    )
    source("Plan based on simulated data (MiroFish + Cortex), with real 2017 audience costs as a benchmark")

# ---------------------------------------------------------------- next button
st.write("")
_, nxt = st.columns([5, 1])
if ch < len(CHAPTERS) - 1 and nxt.button("Next →", use_container_width=True):
    st.session_state.ch = ch + 1
    st.rerun()
