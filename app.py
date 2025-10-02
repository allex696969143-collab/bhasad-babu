import streamlit as st
import re
import pandas as pd
import plotly.express as px
from datetime import datetime
import emoji
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import calmap

# --- Page Configuration ---
st.set_page_config(
    page_title="Love & Friendship Score Analyzer",
    page_icon="💖",
    layout="wide",
)

# --- Core Score Calculation Functions ---

def calculate_lovescore(T, e, m, d):
    """Calculates the LOVE score based on the original theorem."""
    if T < 2: R = 25
    elif T < 5: R = 15
    elif T < 10: R = 10
    elif T < 30: R = 5
    else: R = -15
    if e > 0.5: E = 20
    elif e > 0.2: E = 15
    elif e > 0.1: E = 10
    elif e > 0.05: E = 5
    else: E = 0
    if m > 0.45: M = 15
    elif m > 0.35: M = 10
    elif m > 0.25: M = 5
    else: M = -10
    if d > 0.8: C = 15
    elif d > 0.5: C = 10
    elif d > 0.3: C = 5
    else: C = 0
    lovescore = 50 + R + E + M + C
    return int(lovescore), R, E, M, C

def calculate_friendship_score(T, e, m, d):
    """Calculates a FRIENDSHIP score with a more forgiving reply time metric."""
    if T < 5: R = 20
    elif T < 15: R = 10
    elif T < 60: R = 5
    else: R = 0
    if e > 0.2: E = 20
    elif e > 0.1: E = 15
    elif e > 0.05: E = 10
    else: E = 0
    if m > 0.40: M = 20
    elif m > 0.30: M = 10
    else: M = -5
    if d > 0.6: C = 20
    elif d > 0.3: C = 10
    else: C = 0
    friendship_score = 40 + R + E + M + C
    return int(friendship_score)

# --- Data Parsing and Analysis ---

def parse_chat(chat_file):
    """Parses the uploaded WhatsApp chat file and returns a DataFrame."""
    pattern = re.compile(r'(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}\s?[apAPm\s]*) - ([^:]+): (.*)')
    lines = chat_file.getvalue().decode('utf-8').splitlines()
    data = []
    for line in lines:
        match = pattern.match(line)
        if match:
            date_str, user, message = match.groups()
            user = user.strip()
            try: timestamp = datetime.strptime(date_str, '%d/%m/%Y, %I:%M %p')
            except ValueError:
                try: timestamp = datetime.strptime(date_str, '%m/%d/%y, %I:%M %p')
                except ValueError: continue
            data.append([timestamp, user, message])
    if not data:
        st.error("Could not parse the chat file.")
        return None
    df = pd.DataFrame(data, columns=['timestamp', 'user', 'message'])
    df = df[df['message'] != '<Media omitted>']
    return df

def get_base_metrics(df, user, other_user):
    """Calculates the base metrics (T, e, m, d) for a user."""
    reply_times = []
    for i in range(1, len(df)):
        if df['user'].iloc[i] == user and df['user'].iloc[i-1] == other_user:
            time_diff = (df['timestamp'].iloc[i] - df['timestamp'].iloc[i-1]).total_seconds() / 60
            if time_diff < (60*24): reply_times.append(time_diff)
    T = sum(reply_times) / len(reply_times) if reply_times else 999
    user_messages = df[df['user'] == user]['message']
    emoji_count = sum(c in emoji.EMOJI_DATA for msg in user_messages for c in msg)
    e = emoji_count / len(user_messages) if not user_messages.empty else 0
    m = len(df[df['user'] == user]) / len(df) if len(df) > 0 else 0
    chat_days = df['timestamp'].dt.date.nunique()
    total_days = (df['timestamp'].max() - df['timestamp'].min()).days + 1
    d = chat_days / total_days if total_days > 0 else 0
    return T, e, m, d, reply_times

def analyze_chat_dynamics(df, user1, user2):
    """Analyzes engagement balance between two users."""
    user1_df = df[df['user'] == user1]
    user2_df = df[df['user'] == user2]
    q1_count = user1_df['message'].str.count(r'\?').sum()
    q2_count = user2_df['message'].str.count(r'\?').sum()
    low_effort_replies = [r'\bok\b', r'\bk\b', r'\bhmm\b', r'\blol\b', r'\bhaha\b', r'\byeah\b']
    le1_count = user1_df['message'].str.contains('|'.join(low_effort_replies), case=False).sum()
    le2_count = user2_df['message'].str.contains('|'.join(low_effort_replies), case=False).sum()
    avg_len1 = user1_df['message'].str.len().mean()
    avg_len2 = user2_df['message'].str.len().mean()
    return {"q_count": (q1_count, q2_count), "le_count": (le1_count, le2_count), "avg_len": (avg_len1, avg_len2)}

def get_relationship_status(score):
    if score >= 90: return "💖 Soulmates! 💖", "Your connection is off the charts!", "success"
    elif 75 <= score < 90: return "🔥 The Power Couple 🔥", "You have a fantastic dynamic.", "success"
    elif 60 <= score < 75: return "😊 Besties 😊", "This is a strong, healthy connection.", "info"
    elif 45 <= score < 60: return "🤔 The Slow Burn... 🤔", "There's potential, but it's a bit lukewarm.", "info"
    elif 30 <= score < 45: return "🤷 Just Acquaintances 🤷", "The vibe is pretty casual and infrequent.", "warning"
    else: return "👻 The Ghost Town 👻", "Communication is sparse and heavily imbalanced.", "error"

def analyze_starters(df):
    starters = []
    time_threshold = pd.Timedelta(hours=6)
    if not df.empty:
        starters.append(df['user'].iloc[0])
        for i in range(1, len(df)):
            if (df['timestamp'].iloc[i] - df['timestamp'].iloc[i-1]) > time_threshold:
                starters.append(df['user'].iloc[i])
    return pd.Series(starters).value_counts()

# --- UI and Main App Logic ---
def main():
    st.title("💖 The Ultimate Chat Analyzer 💖")
    st.markdown("Discover the true dynamics of your Love & Friendship connections.")

    uploaded_file = st.file_uploader("Upload your exported WhatsApp chat (.txt)", type="txt")

    if uploaded_file is not None:
        df = parse_chat(uploaded_file)
        if df is not None:
            users = df['user'].unique().tolist()
            if len(users) != 2:
                st.warning("This analysis works best for one-on-one chats."); return

            st.sidebar.header("Analysis Options")
            user1 = st.sidebar.selectbox("Select User 1:", users, index=0)
            user2 = st.sidebar.selectbox("Select User 2:", users, index=1)
            
            if user1 == user2: st.error("Please select two different users."); return

            if st.sidebar.button("💖 Analyze Chat"):
                T1, e1, m1, d1, rt1 = get_base_metrics(df, user1, user2)
                T2, e2, m2, d2, rt2 = get_base_metrics(df, user2, user1)

                lovescore1, R1, E1, M1, C1 = calculate_lovescore(T1, e1, m1, d1)
                lovescore2, R2, E2, M2, C2 = calculate_lovescore(T2, e2, m2, d2)
                friendship_score1 = calculate_friendship_score(T1, e1, m1, d1)
                friendship_score2 = calculate_friendship_score(T2, e2, m2, d2)
                avg_lovescore = (lovescore1 + lovescore2) / 2

                # --- Section 1: Overall Chat Statistics ---
                st.header("📈 Overall Chat Statistics")
                total_messages = len(df)
                total_emojis = sum(c in emoji.EMOJI_DATA for msg in df['message'] for c in msg)
                media_messages = uploaded_file.getvalue().decode('utf-8').count('<Media omitted>')
                conversation_days = df['timestamp'].dt.date.nunique()

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Messages", f"{total_messages} 💬")
                c2.metric("Total Emojis", f"{total_emojis} 😍")
                c3.metric("Media Shared", f"{media_messages} 🖼️")
                c4.metric("Chatting Days", f"{conversation_days} 🗓️")

                # --- Section 2: Scores and Status ---
                st.header("💘 Final Scores & Relationship Status 💘")
                status_title, status_desc, status_type = get_relationship_status(avg_lovescore)
                if status_type == "success": st.success(f"**Overall Status: {status_title}** {status_desc}")
                elif status_type == "info": st.info(f"**Overall Status: {status_title}** {status_desc}")
                else: st.warning(f"**Overall Status: {status_title}** {status_desc}")

                sc1, sc2 = st.columns(2)
                with sc1:
                    st.subheader(f"{user1}'s Scores")
                    st.metric(label="Love Score ❤️", value=lovescore1)
                    st.metric(label="Friendship Score 🤗", value=friendship_score1)
                with sc2:
                    st.subheader(f"{user2}'s Scores")
                    st.metric(label="Love Score ❤️", value=lovescore2)
                    st.metric(label="Friendship Score 🤗", value=friendship_score2)

                # --- Section 3: Engagement Balance ---
                st.header("⚖️ Engagement Balance: Who is More Invested?")
                st.markdown("This section reveals who is truly driving the conversation. A significant imbalance may indicate a lack of selfless interest from one person.")
                dynamics = analyze_chat_dynamics(df, user1, user2)
                q1, q2 = dynamics['q_count']
                le1, le2 = dynamics['le_count']
                avg1, avg2 = dynamics['avg_len']
                
                dc1, dc2, dc3 = st.columns(3)
                dc1.metric(f"Questions Asked by {user1}", int(q1)); dc1.metric(f"Questions Asked by {user2}", int(q2))
                dc2.metric(f"Low-Effort Replies from {user1}", int(le1)); dc2.metric(f"Low-Effort Replies from {user2}", int(le2))
                dc3.metric(f"Avg Msg Length for {user1}", f"{avg1:.1f} chars"); dc3.metric(f"Avg Msg Length for {user2}", f"{avg2:.1f} chars")

                # --- Section 4: All Visualizations ---
                st.header("📊 Dive Deeper into Your Chat History")
                with st.expander("See Conversation Starter & Activity Patterns"):
                    st.subheader("💬 Who Texts First?")
                    starter_counts = analyze_starters(df)
                    st.plotly_chart(px.pie(starter_counts, values=starter_counts.values, names=starter_counts.index, title="Who Initiates the Conversation?"), use_container_width=True)
                    
                    st.subheader("⏰ When Do You Talk The Most?")
                    df['hour'] = df['timestamp'].dt.hour
                    df['day_of_week'] = df['timestamp'].dt.day_name()
                    
                    act1, act2 = st.columns(2)
                    hourly_activity = df['hour'].value_counts().sort_index()
                    act1.plotly_chart(px.bar(hourly_activity, title="Hourly Activity"), use_container_width=True)
                    daily_activity = df['day_of_week'].value_counts().reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                    act2.plotly_chart(px.bar(daily_activity, title="Daily Activity"), use_container_width=True)
                
                with st.expander("See Reply Time Trends"):
                    st.plotly_chart(px.line(y=rt1, title=f"Reply Times for {user1}"), use_container_width=True)
                    st.plotly_chart(px.line(y=rt2, title=f"Reply Times for {user2}"), use_container_width=True)
                
                with st.expander("See Yearly Conversation Heatmap"):
                    df['date'] = df['timestamp'].dt.date
                    activity = df['date'].value_counts()
                    activity.index = pd.to_datetime(activity.index)
                    fig_cal, _ = calmap.calendarplot(activity, cmap='YlGn', fillcolor='lightgrey', fig_kws=dict(figsize=(12, 5)))
                    st.pyplot(fig_cal)
                
                with st.expander("See Top Emojis & Word Clouds"):
                    wc1, wc2 = st.columns(2)
                    for i, (user, user_df) in enumerate([(user1, df[df['user'] == user1]), (user2, df[df['user'] == user2])]):
                        col = wc1 if i == 0 else wc2
                        col.subheader(f"Analysis for {user}")
                        # Emojis
                        emojis_list = [c for msg in user_df['message'] for c in msg if c in emoji.EMOJI_DATA]
                        emoji_df = pd.DataFrame(Counter(emojis_list).most_common(10), columns=['Emoji', 'Count'])
                        col.dataframe(emoji_df)
                        # Word Cloud
                        text = " ".join(msg for msg in user_df['message'])
                        if text:
                            wordcloud = WordCloud(background_color='white').generate(text)
                            fig_wc, ax_wc = plt.subplots()
                            ax_wc.imshow(wordcloud, interpolation='bilinear'); ax_wc.axis('off')
                            col.pyplot(fig_wc)

if __name__ == "__main__":
    main()