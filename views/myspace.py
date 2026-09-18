from Utils.league import *
import streamlit as st
from Params import params as p
import requests
import time

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

tm_data = None

session = requests.Session()

@st.cache_data  
def get_all_data():
    response1 = requests.get(f'{p.base_url}bootstrap-static/')
    if response1.status_code == 200:
        data1 = response1.json()
        players = data1['elements']
        player_dict = {player['id']: [player['web_name'], player['team_code']] for player in players}
        pos = data1['element_types']
        position_dict = {pos['id']: pos['singular_name_short'] for pos in pos}
        teams = data1['teams']
        teams_dict = {team['code']: team['short_name'] for team in teams}
    return player_dict, position_dict, teams_dict
    
import json
import time
import requests
from playwright.sync_api import sync_playwright

TEAM_ID = "2878998"

def get_fpl_authorization_tokens(email, password):
    print("Launching background browser to authenticate...")
    with sync_playwright() as p:
        # headless=True ensures no browser window physically pops up
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 1. Navigate to the FPL login page
        page.goto("https://fantasy.premierleague.com/")

        # Accept cookies banner if it blocks the screen
        if page.locator("button:has-text('Accept All Cookies')").is_visible():
            page.locator("button:has-text('Accept All Cookies')").click()

        # Click the central Log In button that appears before credential fields
        page.locator("button:has-text('Log in')").first.click()

        # Dismiss cookie consent overlay if it blocks interactions
        try:
            page.locator("button:has-text('Confirm My Choices')").click(timeout=5000)
        except Exception:
            pass

        # The account page defaults to "Join myPL"; switch to "Sign In"
        page.locator("button:has-text('Sign In')").first.click()
        time.sleep(1)

        page.fill("input[data-id='username-input']", email)
        page.fill("input[data-id='password-input']", password)

        # 3. Submit the sign-in form and wait for the redirect to complete
        page.locator("button[data-skbuttonvalue='SIGNON']").click()

        for _ in range(30):
            if page.url.startswith("https://fantasy.premierleague.com") and "authorize" not in page.url:
                break
            time.sleep(1)

        time.sleep(5)  # Allow SPA to settle and store tokens

        print("Login complete. Extracting secure tokens...")
        st.session_state["logged_in"] = True

        # Read the access token from the page's localStorage
        storage_script = """
        () => {
            const key = Object.keys(localStorage).find(k => k.startsWith('oidc.user:'));
            return key ? localStorage.getItem(key) : null;
        }
        """
        oidc_data_raw = page.evaluate(storage_script)
        browser.close()

        if oidc_data_raw:
            oidc_data = json.loads(oidc_data_raw)
            return f"Bearer {oidc_data['access_token']}"

        raise Exception("Could not extract token from localStorage. Check email/password.")

if not st.session_state['logged_in'] and not st.session_state.get('bearer_token'):
    email = st.text_input("Enter your email", key='email')
    password = st.text_input("Enter your password", type='password', key='password')
    if st.button("Login"):
        try:
            # Get token automatically via the background browser instance
            bearer_token = get_fpl_authorization_tokens(email, password)
            st.session_state['bearer_token'] = bearer_token
            print("Token secured!")

        except Exception as e:
            print(f"Error: {e}")

if st.session_state['logged_in']:

    # Add title similar to about_me.py
    st.markdown(f'<h1 style="color:#33ff33;font-size:60px;background-image:linear-gradient(45deg, #1A512E, #63A91F);font-family:Montserrat;text-align:left;padding:20px;border-radius:10px;"'
            f'>My FPL Space</h1>', unsafe_allow_html=True)
    
    # Updated tab styling - removed gradient background and set to full width
    st.markdown("""
    <style>
    /* Main tab styling to match the title */
    .stTabs {
        background-color: transparent;
        margin-top: 20px;
        width: 100%;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;  /* Removed gradient */
        border-radius: 10px;
        padding: 8px 0px;
        width: 100%;  /* Full width */
        display: flex;
        justify-content: space-between;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        color: white;
        background-color: rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        font-weight: 500;
        margin: 0;
        padding: 0px 20px;
        border: none;
        transition: all 0.3s;
        flex-grow: 1;  /* Make tabs expand to fill space */
        text-align: center;
    }
    .stTabs [aria-selected="true"] {
        background-color: #33ff33;
        color: #124010;
        font-weight: 600;
    }
    /* Remove default focus outline */
    button:focus {
        outline: none !important;
    }
    
    /* Additional styles from about_me.py */
    .big-font {
        font-size: 20px;
    }
    .st-emotion-cache-sesqrs {
        font-size: 18px;
        color: yellow;
    }
    hr {
        border-color: yellow;
    }
    </style>
    """, unsafe_allow_html=True)

# st.markdown(f'<h1 style="color:#33ff33;font-size:60px;background-image:linear-gradient(45deg, #1A512E, #63A91F);font-family:Montserrat;text-align:left;padding:20px;border-radius:10px;"'
            # f'>My FPL Space</h1>', unsafe_allow_html=True)

st.divider()
# st.header("IN DEVELOPMENT")

mt, pl, an = st.tabs(['My Team', 'Planner', 'Analytics'])

with mt:    
    l = league(581588)
    x = l.get_league_players()

    if st.session_state['logged_in'] and st.session_state.get('bearer_token'):
        # Query the standard FPL API with your freshly acquired token
        team_url = f"https://fantasy.premierleague.com/api/my-team/{TEAM_ID}/"
        headers = {
            "X-Api-Authorization": st.session_state['bearer_token'],
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json"
        }

        response = requests.get(team_url, headers=headers)
        
        if response.status_code == 200:
            tm_data = response.json()
            
        else:
            print(f"API Error: {response.status_code}")

        picks = tm_data['picks']

        pl_data, pos_data, team_data = get_all_data()

        # --- Build formation data ---
        if picks:
            # Group players by position
            formation = {'GKP': [], 'DEF': [], 'MID': [], 'FWD': []}
            for pick in picks:
                player_id = pick['element']
                player_name = pl_data.get(player_id, ["Unknown Player", None])[0]
                player_team = team_data.get(pl_data.get(player_id, [None, None])[1], "Unknown Team")
                pos = pos_data[pick['element_type']]
                if pick['position'] <= 11:
                    formation[pos].append((player_name, player_team))
            col1, col2 = st.columns([15, 1], gap="small")
            with col1:
                st.markdown("""
                <style>
                .row {display: flex; justify-content: center; margin: 18px 0;}
                .player {display: flex; flex-direction: column; align-items: center; margin: 0 18px;}
                .player-icon {font-size: 2.2rem; margin-bottom: 2px;}
                .player-name {font-size: 1.1rem; color: #fff; background: rgba(0,0,0,0.25); border-radius: 8px; padding: 16px 48px; margin-top: 2px;}
                .player-team {font-size: 0.85rem; color: #cccccc; opacity: 0.7; margin-top: 1px;}
                </style>
                """, unsafe_allow_html=True)

                # Helper to get team badge image
                def get_team_badge(team_code):
                    # FPL team codes are 1-indexed, pad to 2 digits
                    return f"https://resources.premierleague.com/premierleague/badges/t{int(team_code):02d}.png"

                # GK
                st.markdown('<div class="formation">' + ''.join([
                    f'<div class="player"><img class="player-icon" src="{get_team_badge(pl_data.get(player_id, [None, team])[1])}" width="36" height="36" style="margin-bottom:2px;"/><span class="player-name">{name}</span><span class="player-team">{team}</span></div>' for (name, team), player_id in zip(formation['GKP'], [pick['element'] for pick in picks if pos_data[pick['element_type']] == 'GKP' and pick['position'] <= 11])
                ]) + '</div>', unsafe_allow_html=True)
                # DEF
                st.markdown('<div class="row">' + ''.join([
                    f'<div class="player"><img class="player-icon" src="{get_team_badge(pl_data.get(player_id, [None, team])[1])}" width="36" height="36" style="margin-bottom:2px;"/><span class="player-name">{name}</span><span class="player-team">{team}</span></div>' for (name, team), player_id in zip(formation['DEF'], [pick['element'] for pick in picks if pos_data[pick['element_type']] == 'DEF' and pick['position'] <= 11])
                ]) + '</div>', unsafe_allow_html=True)
                # MID
                st.markdown('<div class="row">' + ''.join([
                    f'<div class="player"><img class="player-icon" src="{get_team_badge(pl_data.get(player_id, [None, team])[1])}" width="36" height="36" style="margin-bottom:2px;"/><span class="player-name">{name}</span><span class="player-team">{team}</span></div>' for (name, team), player_id in zip(formation['MID'], [pick['element'] for pick in picks if pos_data[pick['element_type']] == 'MID' and pick['position'] <= 11])
                ]) + '</div>', unsafe_allow_html=True)
                # FWD
                st.markdown('<div class="row">' + ''.join([
                    f'<div class="player"><img class="player-icon" src="{get_team_badge(pl_data.get(player_id, [None, team])[1])}" width="36" height="36" style="margin-bottom:2px;"/><span class="player-name">{name}</span><span class="player-team">{team}</span></div>' for (name, team), player_id in zip(formation['FWD'], [pick['element'] for pick in picks if pos_data[pick['element_type']] == 'FWD' and pick['position'] <= 11])
                ]) + '</div>', unsafe_allow_html=True)
        else:
            st.write("No picks found.")

with pl:
    st.write("Planner content goes here.")
    # team_url = 'https://fantasy.premierleague.com/api/my-team/1603111'
    # team_response = session.get(team_url)

    # if team_response.status_code == 200:
    #     # team_data = team_response.json()
    #     tem_data = json.loads(team_response.content)
    #     print(team_data)
    # else:
    #     print(f"Error: {team_response.status_code}")
