import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime, timedelta
import json

st.set_page_config(page_title="Tekoälyvalmentaja", page_icon="🏃‍♂️")
st.title("Tekoälyvalmentaja (Yleinen versio)")
st.write("Tuo oma Intervals.icu -datasi ja kerro taustasi, niin valmentaja räätälöi analyysin sinulle.")

# 1. AVAIMET JA TUNNUKSET (Tyhjät kentät uusille käyttäjille)
st.sidebar.subheader("Asetukset")
api_key = st.sidebar.text_input("Syötä Gemini API-avain", type="password")
athlete_id = st.sidebar.text_input("Intervals.icu Athlete ID")
intervals_api_key = st.sidebar.text_input("Intervals.icu API Key", type="password")

# 2. KÄYTTÄJÄN OMA PROFIILI (Uusi dynaaminen osio)
st.subheader("1. Kerro taustasi")
col1, col2 = st.columns(2)
with col1:
    urheilijan_tyo = st.text_input("Työ / Elämäntilanne", placeholder="Esim. Istumatyö 8-16 tai 24h vuorotyö")
with col2:
    urheilijan_lajit = st.text_input("Lajitausta", placeholder="Esim. Triathlon, kuntosali, tennis")

urheilijan_tavoite = st.text_input("Päätavoite", placeholder="Esim. Peruskunnon kohotus tai maraton alle 4h")

# 3. KYSYMYSKENTTÄ
st.subheader("2. Kysymys valmentajalle")
user_query = st.text_area("Mitä haluat tietää?", 
                          placeholder="Esim. 'Olenko palautunut tarpeeksi huomista kovaa vetotreeniä varten?'")

if st.button("Hae historia ja analysoi"):
    if not api_key or not athlete_id or not intervals_api_key:
        st.error("Syötä kaikki kolme tunnusta vasemman reunan sivupalkkiin!")
    elif not user_query:
        st.warning("Kirjoita kysymys valmentajalle.")
    else:
        with st.spinner('Yhdistetään Intervals.icu-palveluun ja lasketaan kuormitusmalleja...'):
            try:
                # HAETAAN DATA RAJAPINNASTA
                tanaan = datetime.now()
                kuukausi_sitten = (tanaan - timedelta(days=30)).strftime("%Y-%m-%d")
                
                url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/activities?oldest={kuukausi_sitten}"
                response = requests.get(url, auth=('API_KEY', intervals_api_key))
                
                if response.status_code != 200:
                    st.error(f"Rajapintavirhe! Intervals.icu palautti virhekoodin: {response.status_code}. Tarkista tunnukset.")
                    st.stop()
                    
                activities = response.json()
                
                # MATEMAATTINEN KUORMITUKSEN ANALYSOINTI
                akuutti_kesto = 0
                krooninen_kesto = 0
                akuutti_kuorma = 0
                krooninen_kuorma = 0
                yhteenveto_lista = []
                
                for act in activities:
                    pvm_str = act.get('start_date_local', act.get('start_date', ''))[:10]
                    if not pvm_str:
                        continue
                        
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

                # TEKOÄLYN INTEGRAATIO JA DYNAAMINEN PROFIILI
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # Varmistetaan, että tyhjät kentät eivät sekoita tekoälyä
                tausta_tyo = urheilijan_tyo if urheilijan_tyo else "Ei erikseen määritelty"
                tausta_lajit = urheilijan_lajit if urheilijan_lajit else "Yleinen liikunta"
                tausta_tavoite = urheilijan_tavoite if urheilijan_tavoite else "Terveys ja hyvinvointi"
                
                prompt = f"""
                Olet ammattitason urheiluvalmentaja. Ota analyysissä aina huomioon urheilijan antamat taustatiedot:
                - Työ ja elämäntilanne: {tausta_tyo}
                - Lajivalikoima: {tausta_lajit}
                - Tavoite: {tausta_tavoite}
                
                Urheilijan reaaliaikainen fysiologinen kuormitusdata:
                - Akuutti treenimäärä (viimeiset 7 pv): {round(akuutti_kesto / 60, 1)} tuntia (Kokonaiskuorma: {round(akuutti_kuorma)} pistettä)
                - Krooninen pohjakunto (viimeiset 28 pv): {round(krooninen_kesto / 60, 1)} tuntia (Kokonaiskuorma: {round(krooninen_kuorma)} pistettä)
                
                Alla on eriteltynä lista hänen viimeisimmistä harjoituksistaan viimeisen 30 päivän ajalta:
                {json.dumps(yhteenveto_lista, indent=2)}
                
                Urheilijan kysymys: {user_query}
                
                Anna ytimekäs, puhtaasti tähän dataan perustuva fysiologinen analyysi ja ehdotus seuraavista askeleista. 
                Peilaa suosituksia vahvasti urheilijan kertomaan taustaan ja tavoitteeseen.
                """
                
                ai_response = model.generate_content(prompt)
                
                st.success("Treenihistoria noudettu ja analysoitu onnistuneesti!")
                st.write(ai_response.text)
                
            except Exception as e:
                st.error(f"Tapahtui virhe: {e}")