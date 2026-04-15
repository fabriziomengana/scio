import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime
import urllib3

# Disabilita avvisi SSL per evitare errori di connessione su Windows
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# IMPOSTAZIONI DI CONTROLLO
# ==============================================================================
# Metti True per il primo lancio sul PC (scarica tutto lo storico 2025-2026)
# Metti False prima di caricarlo su GitHub (aggiornamento quotidiano veloce)
RECUPERO_STORICO = False  

# Lo script non scaricherà nulla di precedente a questo anno
ANNO_LIMITE_MINIMO = 2025 

# Prefisso per i file salvati (es. data_2026.json)
PREFISSO_FILE = "data_"
# ==============================================================================

def get_extra_details(url, headers):
    """Accede alla scheda dettaglio per recuperare info specifiche"""
    try:
        time.sleep(0.5) # Pausa di sicurezza
        res = requests.get(url, headers=headers, timeout=10, verify=False)
        if res.status_code != 200: return {}
        
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        
        # Estrazione Modalità
        mod_div = detail_soup.find('div', class_='views-field-field-dettagli')
        modalita = mod_div.find('div', class_='field-content').get_text(strip=True) if mod_div else ""
        
        # Estrazione Durata ore
        ore_div = detail_soup.find('div', class_='views-field-field-ore')
        ore = ore_div.find('div', class_='field-content').get_text(strip=True) if ore_div else ""
        
        # Estrazione Note estese
        note_div = detail_soup.find('div', class_='views-field-body')
        note = note_div.find('div', class_='field-content').get_text(strip=True) if note_div else ""

        # Estrazione link ai PDF (Interventi)
        allegati = []
        intervento_section = detail_soup.find('section', id='intervento-section')
        if intervento_section:
            links = intervento_section.find_all('a', href=True)
            for link in links:
                if '.pdf' in link['href'].lower():
                    pdf_url = "https://cgsse.it" + link['href'] if link['href'].startswith('/') else link['href']
                    allegati.append(pdf_url)

        return {"modalita": modalita, "ore": ore, "note": note, "pdf": allegati}
    except:
        return {}

def scrape_cgsse():
    base_url = "https://cgsse.it/calendario-scioperi"
    nuovi_dati = []
    oggi = datetime.now().date()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}

    page = 0
    continua = True

    while continua:
        print(f"Scansione pagina {page}...")
        try:
            res = requests.get(base_url, params={'page': page}, headers=headers, timeout=20, verify=False)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.find_all('li', class_='table-row views-row')
            
            if not rows:
                print("Nessun altro dato trovato.")
                break

            for row in rows:
                # Recupero data inizio
                data_div = row.find('div', class_='views-field-field-data-inizio')
                if not data_div: continue
                data_str = data_div.get_text(strip=True).replace('Data', '').strip()
                
                try:
                    dt_obj = datetime.strptime(data_str, "%d-%m-%Y")
                    data_sciopero = dt_obj.date()
                    anno_sciopero = dt_obj.year
                except: continue

                # 1. STOP DI SICUREZZA (Archivio storico)
                if anno_sciopero < ANNO_LIMITE_MINIMO:
                    print(f"Raggiunto limite anno ({ANNO_LIMITE_MINIMO}). Fine scansione.")
                    continua = False
                    break

                # 2. STOP QUOTIDIANO (GitHub Mode)
                if not RECUPERO_STORICO and data_sciopero < oggi:
                    print(f"Raggiunto sciopero passato ({data_str}). Fine aggiornamento.")
                    continua = False
                    break

                # URL della scheda dettaglio
                link_tag = row.find('a', href=True)
                url_det = "https://cgsse.it" + link_tag['href'] if link_tag else ""
                
                print(f"  -> Recupero dettagli per: {data_str}")
                extra = get_extra_details(url_det, headers) if url_det else {}

                sciopero = {
                    'id_sciopero': url_det.split('/')[-1] if url_det else data_str,
                    'data': data_str,
                    'anno': anno_sciopero,
                    'settore': row.find('div', class_='views-field-nothing-2').get_text(strip=True).replace('Settore', '').strip(),
                    'azienda': row.find('div', class_='views-field-nothing').get_text(strip=True).replace('Azienda', '').strip(),
                    'sindacato': row.find('div', class_='views-field-nothing-5').get_text(strip=True).replace('Sindacato', '').strip(),
                    'ambito': "Nazionale" if row.find('img', alt='sciopero nazionale') else row.find('div', class_='views-field-nothing-1').get_text(strip=True).replace('Ambito geografico', '').strip(),
                    'stato': "Revocato" if row.find('img', alt='sciopero revocato') else "Confermato",
                    'modalita': extra.get('modalita', ''),
                    'ore': extra.get('ore', ''),
                    'note': extra.get('note', ''),
                    'documenti_pdf': extra.get('pdf', []),
                    'url_fonte': url_det
                }
                nuovi_dati.append(sciopero)
            
            page += 1
            
        except Exception as e:
            print(f"Errore durante la scansione: {e}")
            break
            
    return nuovi_dati

def salva_dati(dati):
    """Distribuisce i dati nei file JSON per anno"""
    for s in dati:
        nome_file = f"{PREFISSO_FILE}{s['anno']}.json"
        
        if os.path.exists(nome_file):
            with open(nome_file, 'r', encoding='utf-8') as f:
                archivio = json.load(f)
        else:
            archivio = []

        # Gestione aggiornamento stato (revoche) o nuovo inserimento
        id_esistenti = {str(item['id_sciopero']): i for i, item in enumerate(archivio)}
        my_id = str(s['id_sciopero'])
        
        if my_id in id_esistenti:
            # Aggiorna solo lo stato dello sciopero già salvato
            archivio[id_esistenti[my_id]]['stato'] = s['stato']
        else:
            # Aggiunge il nuovo sciopero
            archivio.append(s)

        # Scrittura su file
        with open(nome_file, 'w', encoding='utf-8') as f:
            json.dump(archivio, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    print("--- AVVIO SCRAPER CGSSE ---")
    dati_estratti = scrape_cgsse()
    if dati_estratti:
        salva_dati(dati_estratti)
        print(f"\nOperazione completata con successo.")
    else:
        print("Nessun nuovo dato da salvare.")
