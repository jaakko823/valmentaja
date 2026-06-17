import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime, timedelta
import json

st.set_page_config(page_title="Tekoälyvalmentaja (Chat)", page_icon="💬")
st.title("Tekoälyvalmentaja 💬")
st.write("Yleiskäyttöinen versio: Valmentaja muistaa keskustelun ja mukautuu kunkin urheilijan omiin tietoihin.")

# 1. AVAIMET JA ASETUKSET SIVUPALKISSA
st.sidebar.subheader("1. Asetukset & Taustatiedot")

# Yritetään hakea Gemini-avain automaattisesti Streamlitin salaisuuksista
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = st.sidebar.text_input("Syötä Gemini API-avain", type="password")

athlete_id = st.sidebar.text_input("Intervals.icu Athlete ID")
intervals_api_key = st.sidebar.text_input("Intervals.icu API Key", type="password")

st.sidebar.markdown("---")
st.sidebar.subheader("2. Urheilijan profiili")
# Kaikki oletusarvot on muutettu neutraaleiksi vihjeteksteiksi (placeholder)
urheilijan_tyo = st.sidebar.text_input("Työ / Elämäntilanne", placeholder="Esim. Vuorotyö, toimistotyö 8-16, tms.")
urheilijan_lajit = st.sidebar.text_input("Lajitausta", placeholder="Esim. Juoksu, kuntosali, uinti, tennis")
urheilijan_tavoite = st.sidebar.text_input("Päätavoite", placeholder="Esim. Peruskunnon kohotus tai tietty kisa")
urheilijan_rajoitteet = st.sidebar.text_area("Pysyvät säännöt ja rajoitteet", 
                                      placeholder="Esim. Tietyt treenipäivät, vammat, laiterajoitukset tai viikkoaikataulut.")

# 2. ALUSTETAAN MUUTTUJAT MUISTIIN (Session State)
if "chat" not in st.session_state:
    st.session_state.chat = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# 3. PAINIKE: HAE DATA DATA JA ALUSTA VALMENTAJA
if st.sidebar.button("Päivitä treenidata ja aloita uusi sessio"):
    if not api_key or not athlete_id or not intervals_api_key:
        st.sidebar.error("Syötä tunnukset ensin!")
    else:
        with st.spinner("Haetaan dataa Intervals.icu:sta..."):
            try:
                # Haetaan data
                tanaan = datetime.now()
                kuukausi_sitten = (tanaan - timedelta(days=30)).strftime("%Y-%m-%d")
                url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/activities?oldest={kuukausi_sitten}"
                response = requests.get(url, auth=('API_KEY', intervals_api_key))
                
                if response.status_code == 200:
                    activities = response.json()
                    
                    akuutti_kesto = 0
                    krooninen_kesto = 0
                    akuutti_kuorma = 0
                    krooninen_kuorma = 0
                    yhteenveto_lista = []
                    
                    for act in activities:
                        pvm_str = act.get('start_date_local', act.get('start_date', ''))[:10]
                        if not pvm_str: continue
                        act_date = datetime.strptime(pvm_str, "%Y-%m-%d")
                        days_ago = (tanaan - act_date).days
                        kesto_min = (act.get('moving_time', 0) or act.get('elapsed_time', 0)) / 60
                        kuorma = act.get('load', 0) if act.get('load') is not None else 0
                        
                        if days_ago <= 7:
                            akuutti_kesto += kesto_min
                            akuutti_kuorma += kuorma
                        if days_ago <= 28:
                            krooninen_kesto += kesto_min
                            krooninen_kuorma += kuorma
                            
                        yhteenveto_lista.append({
                            "laji": act.get('type', 'Tuntematon'),
                            "pvm": pvm_str,
                            "kesto_min": round(kesto_min),
                            "keskisyke": act.get('average_heartrate', 'Ei mitattu'),
                            "kuormitus_pisteet": kuorma
                        })

                    # Rakennetaan tekoälyn "System Instruction" täysin dynaamisesti käyttäjän syötteistä
                    genai.configure(api_key=api_key)
                    
                    system_instruction = f"""Olet ammattitason urheiluvalmentaja, joka keskustelee urheilijan kanssa.
Ota analyyseissä ja ohjelmissa aina huomioon nämä urheilijan ilmoittamat lähtökohdat:
- Työ ja elämäntilanne: {urheilijan_tyo if urheilijan_tyo else 'Ei erikseen määritelty'}
- Lajivalikoima: {urheilijan_lajit if urheilijan_lajit else 'Yleinen kuntoilu'}
- Tavoite: {urheilijan_tavoite if urheilijan_tavoite else 'Yleisen kunnon ja terveyden ylläpito'}
- Rajoitteet ja aikataulut: {urheilijan_rajoitteet if urheilijan_rajoitteet else 'Ei erityisiä rajoitteita ilmoitettu'}

Urheilijan reaaliaikainen fysiologinen kuormitusdata rajapinnasta:
- Akuutti treenimäärä (viimeiset 7 pv): {round(akuutti_kesto / 60, 1)} tuntia (Kokonaiskuorma: {round(akuutti_kuorma)} pistettä)
- Krooninen pohjakunto (viimeiset 28 pv): {round(krooninen_kesto / 60, 1)} tuntia (Kokonaiskuorma: {round(krooninen_kuorma)} pistettä)

Viimeisen 30 päivän harjoitukset:
{json.dumps(yhteenveto_lista, indent=2)}

Vastaa urheilijan viesteihin ammattimaisesti, kannustavasti ja yllä olevaan fysiologiseen dataan perustuen. 
Voit luoda eripituisia harjoitusohjelmia (esim. viikkoja tai kuukausia) ja muokata niitä lennosta, jos urheilija pyytää korjauksia (esim. loukkaantumisten tai menojen vuoksi). Muista tarkasti kaikki, mitä olette aiemmin keskustelussa sopineet."""

                    # Alustetaan Gemini-malli dynaamisella ydinmuistilla
                    model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_instruction)
                    
                    # Käynnistetään uusi chat-sessio ja tyhjennetään vanhat viestit näytöltä
                    st.session_state.chat = model.start_chat(history=[])
                    st.session_state.messages = []
                    
                    st.sidebar.success("✅ Valmentaja alustettu urheilijan tiedoilla!")
                else:
                    st.sidebar.error("Virhe haettaessa dataa Intervals.icu:sta. Tarkista ID ja API-avain.")
            except Exception as e:
                st.sidebar.error(f"Virhe: {e}")

# 4. CHAT-KÄYTTÖLIITTYMÄ (Piirretään viestit näytölle)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. KÄYTTÄJÄN SYÖTEKEHOTE
if st.session_state.chat is None:
    st.info("👈 Täytä taustatiedot sivupalkkiin ja klikkaa 'Päivitä treenidata ja aloita uusi sessio'!")
else:
    prompt = st.chat_input("Kirjoita viesti valmentajalle...")
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("assistant"):
            with st.spinner("Valmentaja miettii..."):
                response = st.session_state.chat.send_message(prompt)
                st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
