import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime, timedelta
import json

st.set_page_config(page_title="Tekoälyvalmentaja", page_icon="🏃‍♂️")
st.title("Tekoälyvalmentaja")
st.write("Tuo oma Intervals.icu -datasi. Valmentaja analysoi kuormituksesi ja laatii halutessasi 4 viikon ohjelman.")

# 1. AVAIMET JA TUNNUKSET (Kysytään aina käyttäjältä)
st.sidebar.subheader("Asetukset")
api_key = st.sidebar.text_input("Syötä Gemini API-avain", type="password")
athlete_id = st.sidebar.text_input("Intervals.icu Athlete ID")
intervals_api_key = st.sidebar.text_input("Intervals.icu API Key", type="password")

# 2. KÄYTTÄJÄN OMA PROFIILI JA TAVOITTEET
st.subheader("1. Kerro taustasi ja tavoitteesi")
col1, col2 = st.columns(2)
with col1:
    urheilijan_tyo = st.text_input("Työ / Elämäntilanne", placeholder="Esim. 24h vuorotyö tai 8-16 toimistotyö")
with col2:
    urheilijan_lajit = st.text_input("Lajitausta", placeholder="Esim. Tennis, uinti, kestävyysjuoksu")

urheilijan_tavoite = st.text_input("Päätavoite", placeholder="Esim. Maratonin aikatavoite tai peruskunnon ylläpito")
urheilijan_rajoitteet = st.text_input("Aikataulut ja laiterajoitteet (vapaaehtoinen)", 
                                      placeholder="Esim. Juoksu mieluiten torstai-aamupäivisin ja crossfit lauantai-aamupäivisin.")

# 3. TOIMINNON VALINTA
st.subheader("2. Valitse valmennuksen tyyppi")
toiminto = st.radio("Mitä haluat valmentajan tekevän?", 
                    ["Analysoi nykytilanne ja anna lyhyt suositus", 
                     "Luo 4 viikon harjoitusohjelma"])

user_query = st.text_area("Lisäkysymykset tai toiveet (vapaaehtoinen)", 
                          placeholder="Esim. 'Huomioi, että ensi viikonloppuna en ehdi treenata lainkaan.'")

if st.button("Hae data ja luo analyysi"):
    if not api_key or not athlete_id or not intervals_api_key:
        st.error("Syötä kaikki kolme tunnusta vasemman reunan sivupalkkiin!")
    else:
        with st.spinner('Yhdistetään Intervals.icu-palveluun ja luodaan sisältöä...'):
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

                # TEKOÄLYN INTEGRAATIO
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # Oletusarvot tyhjille kentille
                tausta_tyo = urheilijan_tyo if urheilijan_tyo else "Ei erikseen määritelty"
                tausta_lajit = urheilijan_lajit if urheilijan_lajit else "Yleinen liikunta"
                tausta_tavoite = urheilijan_tavoite if urheilijan_tavoite else "Terveys ja hyvinvointi"
                tausta_rajoitteet = urheilijan_rajoitteet if urheilijan_rajoitteet else "Ei erityisiä rajoitteita"
                lisakysymys = user_query if user_query else "Ei lisättyjä toiveita."
                
                # Muutetaan tekoälyn tehtävänantoa valinnan mukaan
                if toiminto == "Luo 4 viikon harjoitusohjelma":
                    tehtavananto = """
                    Laadi urheilijalle selkeä 4 viikon harjoitusohjelma taulukkomuodossa. 
                    - Viikko 1 alkaa välittömästi nykyisestä kuormitustilasta. Jos urheilija on ylirasittunut, aloita kevyesti.
                    - Jaa jokainen viikko päiväkohtaisesti (Maanantai-Sunnuntai).
                    - Määrittele jokaiselle treenille kesto, laji ja intensiteetti.
                    - Huomioi ehdottomasti urheilijan tavoite, aikataulurajoitteet ja laitetoiveet.
                    - Perustele lyhyesti ohjelman lopussa, miksi ohjelma on rytmitetty näin suhteessa pohjakuntoon.
                    """
                else:
                    tehtavananto = """
                    Anna ytimekäs, puhtaasti dataan perustuva fysiologinen analyysi ja ehdotus seuraavista askeleista 
                    (tälle ja huomiselle päivälle). Arvioi akuutin kuorman suhdetta krooniseen pohjaan ja peilaa sitä tavoitteeseen.
                    """
                
                prompt = f"""
                Olet ammattitason urheiluvalmentaja. Ota analyysissä aina huomioon urheilijan antamat taustatiedot:
                - Työ ja elämäntilanne: {tausta_tyo}
                - Lajivalikoima: {tausta_lajit}
                - Tavoite: {tausta_tavoite}
                - Rajoitteet ja aikataulut: {tausta_rajoitteet}
                
                Urheilijan reaaliaikainen fysiologinen kuormitusdata:
                - Akuutti treenimäärä (viimeiset 7 pv): {round(akuutti_kesto / 60, 1)} tuntia (Kokonaiskuorma: {round(akuutti_kuorma)} pistettä)
                - Krooninen pohjakunto (viimeiset 28 pv): {round(krooninen_kesto / 60, 1)} tuntia (Kokonaiskuorma: {round(krooninen_kuorma)} pistettä)
                
                Alla on eriteltynä lista hänen viimeisimmistä harjoituksistaan viimeisen 30 päivän ajalta:
                {json.dumps(yhteenveto_lista, indent=2)}
                
                Lisätoive urheilijalta: {lisakysymys}
                
                TEHTÄVÄ:
                {tehtavananto}
                """
                
                ai_response = model.generate_content(prompt)
                
                st.success("Analyysi suoritettu onnistuneesti!")
                st.write(ai_response.text)
                
            except Exception as e:
                st.error(f"Tapahtui virhe: {e}")
