import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime, timedelta
import json

st.set_page_config(page_title="Tekoälyvalmentaja", page_icon="🏃‍♂️")
st.title("Tekoälyvalmentaja")
st.write("Tuo oma Intervals.icu -datasi. Valmentaja analysoi kuormituksesi ja laatii harjoitusohjelman.")

# 1. AVAIMET JA TUNNUKSET
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

urheilijan_tavoite = st.text_input("Päätavoite ja sen ajankohta", placeholder="Esim. Syyskuun maraton tai peruskunnon ylläpito")
urheilijan_rajoitteet = st.text_input("Aikataulut ja laiterajoitteet (vapaaehtoinen)", 
                                      placeholder="Esim. Juoksu mieluiten torstai-aamupäivisin. Kävelymatolla vain kävelyä.")

# 3. TOIMINNON VALINTA (Päivitetty pudotusvalikoksi)
st.subheader("2. Valitse valmennuksen tyyppi")
toimintovaihtoehdot = [
    "Analysoi nykytilanne ja anna lyhyt suositus",
    "Luo 4 viikon harjoitusohjelma",
    "Luo 3 kuukauden harjoitusohjelma",
    "Luo 6 kuukauden harjoitusohjelma",
    "Luo 12 kuukauden harjoitusohjelma"
]
toiminto = st.selectbox("Mitä haluat valmentajan tekevän?", toimintovaihtoehdot)

user_query = st.text_area("Lisätoiveet tai muutokset ohjelmaan (vapaaehtoinen)", 
                          placeholder="Esim. 'Loukkasin nilkan, korvaa juoksu uinnilla seuraavat 2 viikkoa.'")

if st.button("Hae data ja luo analyysi"):
    if not api_key or not athlete_id or not intervals_api_key:
        st.error("Syötä kaikki kolme tunnusta vasemman reunan sivupalkkiin!")
    else:
        with st.spinner('Yhdistetään Intervals.icu-palveluun ja luodaan valmennussuunnitelmaa...'):
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
                
                tausta_tyo = urheilijan_tyo if urheilijan_tyo else "Ei erikseen määritelty"
                tausta_lajit = urheilijan_lajit if urheilijan_lajit else "Yleinen liikunta"
                tausta_tavoite = urheilijan_tavoite if urheilijan_tavoite else "Terveys ja hyvinvointi"
                tausta_rajoitteet = urheilijan_rajoitteet if urheilijan_rajoitteet else "Ei erityisiä rajoitteita"
                lisakysymys = user_query if user_query else "Ei lisättyjä toiveita."
                
                # Dynaaminen promptin rakennus valitun aikajänteen mukaan
                if toiminto == "Luo 4 viikon harjoitusohjelma":
                    tehtavananto = """
                    Laadi urheilijalle selkeä 4 viikon harjoitusohjelma taulukkomuodossa. 
                    Jaa jokainen viikko päiväkohtaisesti (Maanantai-Sunnuntai).
                    Määrittele jokaiselle treenille kesto, laji ja intensiteetti.
                    Huomioi ehdottomasti urheilijan antamat aikataulurajoitteet.
                    """
                elif toiminto in ["Luo 3 kuukauden harjoitusohjelma", "Luo 6 kuukauden harjoitusohjelma", "Luo 12 kuukauden harjoitusohjelma"]:
                    tehtavananto = f"""
                    Laadi urheilijalle ammattimainen {toiminto.split(' ')[1]} kuukauden harjoitussuunnitelma (makrosykli).
                    Koska aikajänne on pitkä, älä tee päivätason taulukkoa koko ajalle, vaan toimi näin:
                    1. Jaa ohjelma selkeisiin harjoituskausiin (esim. peruskuntokausi, voimakausi, kilpailuun valmistava kausi).
                    2. Määrittele jokaisen kauden päätavoite, kesto ja viikoittainen rytmitys.
                    3. Rakenna lopuksi yksi eritelty ja tarkka esimerkkiviikko (Maanantai-Sunnuntai) ohjelman ensimmäiselle kaudelle taulukkomuodossa, jotta urheilija tietää, miten aloittaa huomenna.
                    Huomioi suunnitelmassa urheilijan ilmoittamat tavoitteet ja rajoitteet.
                    """
                else:
                    tehtavananto = """
                    Anna ytimekäs, puhtaasti dataan perustuva fysiologinen analyysi nykytilanteesta.
                    Arvioi akuutin kuorman suhdetta krooniseen pohjaan ja anna ehdotus seuraavien päivien treeneistä tavoitteeseen peilaten.
                    """
                
                prompt = f"""
                Olet ammattitason urheiluvalmentaja. Ota analyysissä aina huomioon urheilijan antamat taustatiedot:
                - Työ ja elämäntilanne: {tausta_tyo}
                - Lajivalikoima: {tausta_lajit}
                - Tavoite ja aikataulu: {tausta_tavoite}
                - Rajoitteet ja aikataulut: {tausta_rajoitteet}
                
                Urheilijan reaaliaikainen fysiologinen kuormitusdata:
                - Akuutti treenimäärä (viimeiset 7 pv): {round(akuutti_kesto / 60, 1)} tuntia (Kokonaiskuorma: {round(akuutti_kuorma)} pistettä)
                - Krooninen pohjakunto (viimeiset 28 pv): {round(krooninen_kesto / 60, 1)} tuntia (Kokonaiskuorma: {round(krooninen_kuorma)} pistettä)
                
                Alla on eriteltynä lista hänen viimeisimmistä harjoituksistaan viimeisen 30 päivän ajalta:
                {json.dumps(yhteenveto_lista, indent=2)}
                
                Lisätoive, tilannepäivitys tai loukkaantuminen: {lisakysymys}
                
                TEHTÄVÄ:
                {tehtavananto}
                """
                
                ai_response = model.generate_content(prompt)
                
                st.success("Suunnitelma laadittu onnistuneesti!")
                st.write(ai_response.text)
                
            except Exception as e:
                st.error(f"Tapahtui virhe: {e}")
