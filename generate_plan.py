import requests
import csv
import io
import pandas
from datetime import datetime
from selenium import webdriver
import time
import os
import logging
import argparse
import json
from selenium.common import NoSuchElementException
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC, wait
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service as EdgeService

import gChatcopack
gv_username = os.getlogin()
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
pandas.set_option('display.max_rows', None)
pandas.set_option('display.max_columns', None)
pandas.set_option('display.width', None)
pandas.set_option('display.max_colwidth', None)
pandas.set_option('display.float_format', '{:.2f}'.format)

gsheet_csv_url_plan_mte = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTxb2kr0rI6nFEPJ_FxgtiPkmjYa9uEcDoF4ZWXUQ1xtwDT_HBjf2ZGCElxYhBNK4oLXKLnDdsXyPAm/pub?gid=1182346047&single=true&output=csv'
gsheet_csv_url_plan_lnp = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTxb2kr0rI6nFEPJ_FxgtiPkmjYa9uEcDoF4ZWXUQ1xtwDT_HBjf2ZGCElxYhBNK4oLXKLnDdsXyPAm/pub?gid=1624923434&single=true&output=csv'
gsheet_csv_url_zlec_mte = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTxb2kr0rI6nFEPJ_FxgtiPkmjYa9uEcDoF4ZWXUQ1xtwDT_HBjf2ZGCElxYhBNK4oLXKLnDdsXyPAm/pub?gid=855261595&single=true&output=csv'


def get_data_from_gsheet(url):
    """Pobiera i parsuje dane z arkusza Google Sheets uwzględniając nowe kolumny (G-L)."""
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()
        content_string = response.content.decode('utf-8')

        df = pandas.read_csv(io.StringIO(content_string))

        print("Oryginalne kolumny z Sheets:", df.columns.tolist())

        mapping = {
            'Ilość kartonów': 'quantity',
            'Lokalizacja': 'location_code',
            'Item': 'item_id',
            'SSCC': 'sscc',
            'Ilość sztuk': 'total_pieces'
        }

        for sheet_name, internal_name in mapping.items():
            if sheet_name in df.columns:
                df.rename(columns={sheet_name: internal_name}, inplace=True)

        if 'quantity' not in df.columns or 'location_code' not in df.columns:
            if len(df.columns) >= 6:
                df.rename(columns={df.columns[4]: 'quantity', df.columns[5]: 'location_code'}, inplace=True)

        if 'quantity' in df.columns and 'location_code' in df.columns:
            df['quantity'] = pandas.to_numeric(df['quantity'], errors='coerce').fillna(0).astype('Int64')
            df['location_code'] = df['location_code'].astype(str).replace('nan', '')
            if 'sscc' in df.columns:
                df['sscc'] = df['sscc'].astype(str).replace('nan', '')
        else:
            raise ValueError(f"Nie znaleziono kluczowych kolumn. Dostępne: {df.columns.tolist()}")
        print("=========================================================")
        print("Przetworzone kolumny:", df.columns.tolist())
        print("=========================================================")
        return df
    except Exception as e:
        print(f"Błąd w get_data_from_gsheet: {e}")
        return None
def download_wait(path_OS):
    seconds = 0
    dl_wait = True
    while dl_wait and seconds < 20:
        time.sleep(1)
        dl_wait = False
        for fname in os.listdir(path_OS):
            if fname.endswith('.crdownload'):
                dl_wait = True
        seconds += 1
    return seconds
def browser_configuration():
    options = Options()
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-extensions')
    options.add_argument('--start-maximized')
    prefs = {'profile.default_content_settings.popups': 0}
    options.add_experimental_option("prefs", prefs)
    return options
def main_MTE():
    global gsheet_csv_url_plan_mte
    #gsheet_csv_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTxb2kr0rI6nFEPJ_FxgtiPkmjYa9uEcDoF4ZWXUQ1xtwDT_HBjf2ZGCElxYhBNK4oLXKLnDdsXyPAm/pub?gid=1182346047&single=true&output=csv'

    df = get_data_from_gsheet(gsheet_csv_url_plan_mte)
    #print(df.columns)
    #exit()
    if df is not None:
            print("Dane pobrane i sparsowane pomyślnie:")
            podsumowanie_msg = f"🤖Robot copackingu zaczyna prace! "
            gChatcopack.wyslij_powiadomienie_do_chata(podsumowanie_msg)
            print(df)
    else:
            print("Nie udało się pobrać danych. Sprawdź URL lub ustawienia udostępniania.")
            podsumowanie_msg = f"🤖Robot copackingu nie moze odczytac plik "
            gChatcopack.wyslij_powiadomienie_do_chata(podsumowanie_msg)
    #df.rename(columns={'Unnamed: 4': 'quantity', 'Unnamed: 5': 'location_code'}, inplace=True)

        # Konwersja kolumn na odpowiednie typy danych
    df['Item'] = pandas.to_numeric(df['item_id'], errors='coerce').astype('Int64')
    df['Ilość kartonów'] = pandas.to_numeric(df['quantity'], errors='coerce').astype('Int64')
    df['Numer Recepcji'] = df['Numer Recepcji'].astype(str)
    df['location_code'] = df['location_code'].astype(str)
    # 1. Zamień na tekst i uzupełnij do 11 znaków zerami z PRZODU (zfill)
    df['location_code'] = df['location_code'].astype(str).str.replace(r'\.0$', '', regex=True)
    df['location_code'] = df['location_code'].str.zfill(12)

    # 2. Teraz tniemy sztywno według Twojego schematu: 0174 | 001 | 10 | 03
    df['alley'] = df['location_code'].str[0:4]  # '0174'
    df['face'] = df['location_code'].str[4]  # '.' (kropka to Face)
    df['przeslo'] = df['location_code'].str[5:8]  # '001' (Column)
    df['level'] = df['location_code'].str[8:10]  # '10'
    df['lokal'] = df['location_code'].str[10:13]  # '03'
    # Parsowanie kodu lokalizacji na poszczególne elementy
    #df['alley'] = df['location_code'].str[:5]
    #df['face'] = df['location_code'].str[4]
    #df['przeslo'] = df['location_code'].str[5:8]
    #df['level'] = df['location_code'].str[8:10]
    #df['lokal'] = df['location_code'].str[10:12]
    service = EdgeService(executable_path=fr"C:\\Users\\{gv_username}\\Downloads\\msedgedriver.exe")
    browser = webdriver.Edge(service=service, options=browser_configuration())
    browser.implicitly_wait(10)
    try:
        for index,row in df.iterrows():

            # testowe
            #browser.get('http://sgeqrfxap25.fmlogistic.fr:18120/reflex/env/QSBERFX254')
            #prod
            browser.get('http://psberfx2.fmlogistic.fr:18080/reflex/logout.jsp')
            #item_id = str(row['Ilość itemów na stendzie'])
            #location = str(row['Unnamed: 5'])
            #quantity = str(row['Unnamed: 4'])
            #nr_rec= str(row['Numer Recepcji'])
            alley = row["alley"]
            face = row["face"]
            przeslo = row["przeslo"]
            level = row['level']
            lokal = row['lokal']
            quantity = row['quantity']


            time.sleep(20)
            try:
                logger.debug("Logowanie")
                browser.find_element(By.XPATH, "/html/body/div/a").click()
                logger.debug("ENTER")
            except:pass
            try:
                browser.find_element(By.XPATH, "/html/body/div[4]/div/input[1]").send_keys("YIVANO")
                browser.find_element(By.XPATH, "/html/body/div[4]/div/input[2]").send_keys("YI1234")
                browser.find_element(By.XPATH, "/html/body/div[4]/div/span").click()
                logger.info("ZALOGOWANO")
            except Exception as e:
                logger.error(f"Blad logowania: {e}")
            try:
                logger.error(f"Nowa sesja: ")
                browser.find_element(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[4]/div[4]/button[2]/div").click()
            except Exception as e:
                logger.error(f"Blad nowej sesji: {e} lub niema potrzeby")
            r = 12
            time.sleep(2)
            while r != 6:
                try:

                    browser.find_element("xpath",
                                         f"/ html / body / div[2] / div[1] / div[1] / div[{r}] / div[1] / table / tbody / tr / td[3] / div / span[5]").click()
                    print("zamyka", r)

                    r -= 1


                except:
                    print("Nie zamyka", r)
                    r -= 1
            try:

                wait = WebDriverWait(browser, 15)


                pick_batches_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[3]/table/tbody/tr/td[2]")))
                pick_batches_button.click()
                print("Przycisk został kliknięty pomyślnie")
            except Exception as e:
                print(f"Błąd podczas wyszukiwania elementu: {e}")
            print("click pick batches", str(datetime.now()))
            time.sleep(2)
            try:
                # change_client

                #
                client_path = f"/html/body/div[2]/div[1]/div[1]/div[7]/div[4]/div[10]"
                client_val = browser.find_element(By.XPATH, client_path).text.strip()

                print(f"➡️ {client_val}")
                if client_val!="MATTEL":
                    try:browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[7]/div[4]/button[6]/div").click()
                    except:browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/button[6]/div").click()
                    #/html/body/div[2]/div[1]/div[1]/div[7]/div[4]/button[6]/div
                    #/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/button[6]/div
                    time.sleep(5)
                    browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[6]/div[1]/input").click()
                    #/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[6]/div[1]/input
                    actions = ActionChains(browser)

                    def create_safe_xpath(text_to_search):
                        """Tworzy XPATH z użyciem concat(), aby bezpiecznie obsługiwać apostrofy (').
                        Celuje w element listy: //div[contains(@class, 'a-combomenuiteminner')].
                        """
                        # Używamy konkretnego elementu listy z Twojego zrzutu ekranu
                        XPATH_PREFIX = "//div[contains(@class, 'a-combomenuiteminner') and contains(text(), "

                        if "'" not in text_to_search:
                            # Prosty XPATH, jeśli nie ma apostrofów
                            return f"{XPATH_PREFIX}'{text_to_search}')]"

                        # Jeśli są apostrofy, musimy użyć funkcji concat() w XPATH
                        parts = text_to_search.split("'")
                        xpath_parts = [f"'{part}'" for part in parts]
                        final_xpath_value = ',"\'",'.join(xpath_parts)

                        return f"{XPATH_PREFIX}concat({final_xpath_value}))]"

                    try:
                        actywnosc = browser.find_element(By.XPATH, f"//*[contains(text(), 'MTE')]")
                        time.sleep(5)
                        actywnosc.click()
                    except:
                        # 1. Zbuduj XPATH bezpieczny dla apostrofów, celujący w jeden element
                        xpath_activity_item = create_safe_xpath("MTE")

                        print(f"Szukam aktywności za pomocą XPATH: {xpath_activity_item}")

                        # 2. Oczekuj na klikalność (co oznacza, że lista jest już załadowana)
                        activity_element = wait.until(
                            EC.element_to_be_clickable((By.XPATH, xpath_activity_item)),
                            message=f"Aktywność 'MTE' nie jest widoczna lub klikalna."
                        )

                        # 3. Kliknij znaleziony element
                        activity_element.click()

                        print(f"✅ Wybrana zostala aktywnosc - MTE (za pomocą bezpośredniego XPATH)")

                    time.sleep(5)


                    try:
                        actywnosc.send_keys(Keys.ENTER)
                    except:
                        browser.find_element(By.XPATH,
                                             f"/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/button[1]").click()
                    print("Wybrana zostala aktywnosc - MTE")
            except:
                    print("aktywnosc nie zostala wybrana")

            #klick location
            browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[1]/div[4]/div/div[3]/span[2]").click()
            time.sleep(2)
            #alley
            browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[7]/div/input").send_keys(alley)
            time.sleep(2)
            #face(.)
            browser.find_element(By.XPATH,f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[8]/div/input").send_keys(face)
                                                    #/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[8]/div/input
            time.sleep(2)
            #column
            browser.find_element(By.XPATH,f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[9]/div/input").send_keys(przeslo)
            time.sleep(2)
            #level
            browser.find_element(By.XPATH,f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[10]/div/input").send_keys(level)
            #location
            time.sleep(2)
            okey=browser.find_element(By.XPATH,f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[11]/div/input")
            okey.send_keys(lokal)
            #enter +enter

            time.sleep(2)
            #ok_button = browser.find_element(By.XPATH, '/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/button[2]/div')


            okey.send_keys(Keys.RETURN, Keys.RETURN)
            time.sleep(5)
            #okey.click()
            #rclick

            try:
                mission_count_element=browser.find_element(By.XPATH,
                             f"/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[12]/div[2]/div/div[2]/table/tr/td[2]")
                actions = ActionChains(browser)
                actions.context_click(mission_count_element).perform()
                time.sleep(2)
                try:
                    wait = WebDriverWait(browser, 10)

                    print("Czekam na pojawienie się kontenera menu...")

                    menu_container = wait.until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, "div.dijitMenuPopup")))

                    print("Kontener menu widoczny. Szukam opcji 'Break down...' wewnątrz.")
                    modify_option = menu_container.find_element(By.XPATH, ".//td[contains(text(), 'Break down...')]")
                    modify_option.click()
                    print("Udało się kliknąć 'Modify...'.")


                except Exception as e:
                    print(f"❌ Nie udało się znaleźć kontenera menu. Błąd: {e}")
                time.sleep(5)

                verify = browser.find_element(By.XPATH,
                                              f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[66]/div/input").get_attribute(
                    "value")

                print(f"Pobrana wartość do weryfikacji: '{verify}'")
                print(f"Wymagana ilość: '{quantity}'")

                if verify:
                    if int(verify)!=0 and int(verify) < int(quantity) and verify!="" :
                        print("Ilość do weryfikacji jest większa niż wymagana. Zakończenie skryptu.")
                        exit()
                else:
                    print("Wartość do weryfikacji jest pusta. Zakończenie skryptu.")


                browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[72]/div/input").send_keys(
                    quantity)
                oki=browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[81]/div/div[1]/input").click()
                time.sleep(2)
                #ok_button = browser.find_element(By.XPATH, "//*[text()='OK']")

                try:
                    browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[84]/div/input").clear()
                    browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[84]/div/input").send_keys("COP")
                except Exception as e:
                    print(e,"pass 1")
                    pass
                try:
                    browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[85]/div/input").clear()
                    browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[85]/div/input").send_keys(" ")
                except Exception as e:
                    print(e,"pass 2")
                    pass
                try:
                    browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[86]/div/input").clear()
                    browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[86]/div/input").send_keys(" ")
                except Exception as e:
                    print(e,"pass 3")
                    pass
                try:

                    element_to_clear=browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[87]/div/input")
                    element_to_clear.send_keys(Keys.CONTROL + "a")
                    element_to_clear.send_keys(Keys.DELETE)
                    #element_to_clear.send_keys("COP")
                except Exception as e:
                    print(e, "pass 4")
                    pass
                try:
                    browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[88]/div/input").clear()
                except Exception as e:
                    print(e, "pass 4")
                    pass
                print("SPRAWDZAMY na szybko")
                time.sleep(20)
                print("SPRAWDZAMY koniec")
                try:
                    browser.find_element(By.XPATH,f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/button[9]/div").click()
                except:
                    print("1 nie kliknelo confirm")
                time.sleep(2)
                try:
                    browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/button[9]/div").click()
                except:
                    print("2 nie kliknelo confirm")

                try:

                    WebDriverWait(browser, 15).until(
                        EC.presence_of_element_located((By.XPATH, "/html/body/div[2]"))
                    )

                    # Po upewnieniu się, że okno się pojawiło, wyślij ENTER do aktywnego elementu
                    browser.switch_to.active_element.send_keys(Keys.RETURN)
                    logging.info("Potwierdzono okno dialogowe za pomocą klawisza Enter.")
                    # Po upewnieniu się, że okno się pojawiło, wyślij ENTER do aktywnego elementu
                    browser.switch_to.active_element.send_keys(Keys.RETURN)
                    logging.info("Potwierdzono okno dialogowe za pomocą klawisza Enter.")
                except Exception as e:
                    logging.error(f"Wystąpił błąd podczas próby potwierdzenia Enterem: {e}")
                    pass
                time.sleep(2)
                print("czekamy aaccept")

            except Exception as e:
                print("nie udalo sie znalesc palety",e)
                continue

        podsumowanie_msg = f"🤖Podrezerwowano {len(df)} pozycji! "
        gChatcopack.wyslij_powiadomienie_do_chata(podsumowanie_msg)
        change_grade("MTE")
        #browser.close()

    except Exception as e:
       print("skip step", e)
       pass
    #except Exception as e:
    #    print(e)
    #browser.close()
def zamknij_wszystkie_okna_do_zera(browser):
    """Bezwzględne czyszczenie pulpitu ze wszystkich otwartych okien Reflexa."""
    browser.implicitly_wait(3)
    logger.info("--- CZYSZCZENIE PULPITU DO WARSTWY BASE (r=6) ---")
    for _ in range(2):
        r = 16
        while r >= 6:
            try:
                btn = browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[{r}]/div[1]/table/tbody/tr/td[3]/div/span[5]")
                if btn.is_displayed():
                    btn.click()
                    print(f"ZAMKNIĘTO OKNO r={r}")
                    time.sleep(0.3)
            except:
                print(f"NIE ZAMKNIĘTO OKNO r={r}")
            r -= 1
    browser.implicitly_wait(30)


def main_LNP(x):
    global gsheet_csv_url_plan_lnp

    df = get_data_from_gsheet(gsheet_csv_url_plan_lnp)
    print(df)
    if df is not None:
        gChatcopack.wyslij_powiadomienie_do_chata("UWAGA TEST!!!!!! Dane pobrane i sparsowane pomyślnie:")
        print(df)
    else:
        print("Nie udało się pobrać danych. Sprawdź URL lub ustawienia udostępniania.")
        return

    # Konwersja kolumn
    df['quantity'] = pandas.to_numeric(df['quantity'], errors='coerce').astype('Int64')
    df['location_code'] = df['location_code'].astype(str).str.replace(r'\.0$', '', regex=True)
    df['location_code'] = df['location_code'].str.zfill(12)

    # Parsowanie lokalizacji
    df['alley'] = df['location_code'].str[:4]
    df['face'] = df['location_code'].str[4]
    df['przeslo'] = df['location_code'].str[5:8]
    df['level'] = df['location_code'].str[8:10]
    df['lokal'] = df['location_code'].str[10:13]

    service = EdgeService(executable_path=fr"C:\Users\{gv_username}\Downloads\msedgedriver.exe")
    browser = webdriver.Edge(service=service, options=browser_configuration())
    browser.implicitly_wait(10)

    try:
        for index, row in df.iterrows():
            gChatcopack.wyslij_powiadomienie_do_chata(f"--- START PROCESOWANIA WIERSZA NR: {index + 1} z {len(df)} ---")

            alley = row["alley"]
            face = row["face"]
            przeslo = row["przeslo"]
            level = row['level']
            lokal = row['lokal']
            quantity = row['quantity']
            sscc = row.get('sscc', '-')

            if "BRAK" in str(alley):
                logger.info(f"Pominięto wiersz {index + 1} - BRAK w lokalizacji.")
                continue

            try:
                browser.get('http://sgeqrfxap25.fmlogistic.fr:18120/reflex/env/QSBERFX254')
                time.sleep(2)

                try:
                    browser.find_element(By.XPATH, "/html/body/div/a").click()
                except:
                    pass

                try:
                    browser.find_element(By.XPATH, "/html/body/div[4]/div/input[1]").send_keys("YIVANO")
                    browser.find_element(By.XPATH, "/html/body/div[4]/div/input[2]").send_keys("YI1234")
                    browser.find_element(By.XPATH, "/html/body/div[4]/div/span").click()
                    logger.info("ZALOGOWANO")
                except:
                    pass

                try:
                    browser.find_element(By.XPATH,
                                         "/html/body/div[2]/div[1]/div[1]/div[4]/div[4]/button[2]/div").click()
                except:
                    pass

                precyzyjne_zamykanie_skanera(browser)

                wait = WebDriverWait(browser, 15)
                try:
                    pick_btn = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, "/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[2]/table/tbody/tr/td[2]")))
                    pick_btn.click()
                except:
                    browser.find_element(By.XPATH,
                                         "/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[3]/table/tbody/tr/td[2]").click()

                time.sleep(3)

                y = None
                for temp_y in range(6, 16):
                    try:
                        loc_btn = browser.find_element(By.XPATH,
                                                       f"/html/body/div[2]/div[1]/div[1]/div[{temp_y}]/div[4]/div[1]/div[1]/div[4]/div/div[3]/span[2]")
                        if loc_btn.is_displayed():
                            loc_btn.click()
                            y = temp_y
                            break
                    except:
                        continue

                if y is None:
                    logger.error(f"❌ Nie odnaleziono kontenera Location dla wiersza {index + 1}")
                    continue

                time.sleep(1)

                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[7]/div/input").send_keys(
                    alley)
                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[8]/div/input").send_keys(
                    face)
                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[9]/div/input").send_keys(
                    przeslo)
                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[10]/div/input").send_keys(
                    level)

                okey = browser.find_element(By.XPATH,
                                            f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[11]/div/input")
                okey.send_keys(lokal)
                okey.send_keys(Keys.RETURN, Keys.RETURN)

                time.sleep(3)

                mission_count_element = wait.until(
                    EC.presence_of_element_located((By.XPATH,
                                                    f"/html/body/div[2]/div[1]/div[1]/div[{y + 1}]/div[4]/div[12]/div[2]/div/div[2]/table/tr/td[2]"))
                )
                actions = ActionChains(browser)
                actions.context_click(mission_count_element).perform()

                menu_container = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.dijitMenuPopup")))
                menu_container.find_element(By.XPATH, ".//td[contains(text(), 'Break down...')]").click()

                time.sleep(2)

                try:
                    verify = browser.find_element(By.XPATH,
                                                  f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[66]/div/input").get_attribute(
                        "value")
                    if verify and int(verify) != 0 and int(verify) < int(quantity):
                        logger.warning(
                            f"Ilość do weryfikacji ({verify}) mniejsza niż wymagana ({quantity}). Pomijanie wiersza {index + 1}.")
                        ActionChains(browser).send_keys(Keys.ESCAPE).perform()
                        continue
                except:
                    pass

                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[72]/div/input").send_keys(
                    str(quantity))
                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[81]/div/div[1]/input").click()
                time.sleep(1)

                try:
                    c1 = browser.find_element(By.XPATH,
                                              f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[84]/div/input")
                    c1.clear()
                    c1.send_keys("COPA")
                except:
                    pass

                try:
                    c2 = browser.find_element(By.XPATH,
                                              f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[85]/div/input")
                    c2.clear()
                    c2.send_keys(".")
                except:
                    pass

                try:
                    c3 = browser.find_element(By.XPATH,
                                              f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[86]/div/input")
                    c3.clear()
                    c3.send_keys(x)
                except:
                    pass

                try:
                    el_clear = browser.find_element(By.XPATH,
                                                    f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[87]/div/input")
                    el_clear.send_keys(Keys.CONTROL + "a", Keys.DELETE)
                except:
                    pass

                try:
                    browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[88]/div/input").clear()
                except:
                    pass

                try:
                    elements = browser.find_elements(By.XPATH,
                                                     f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[91]/div/div[1]/input[not(@checked)]")
                    if elements: elements[0].click()
                except:
                    pass

                time.sleep(1)
                try:
                    browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/button[9]/div").click()
                except:
                    pass
                time.sleep(1)
                try:
                    browser.find_element(By.XPATH,
                                         f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/button[9]/div").click()
                except:
                    pass

                time.sleep(1)
                try:
                    browser.switch_to.active_element.send_keys(Keys.RETURN)
                    browser.switch_to.active_element.send_keys(Keys.RETURN)
                except:
                    pass

                time.sleep(2)

                logger.info("Rozpoczynam procedurę HOLD...")

                mission_elem_refreshed = wait.until(
                    EC.presence_of_element_located((By.XPATH,
                                                    f"/html/body/div[2]/div[1]/div[1]/div[{y + 1}]/div[4]/div[12]/div[2]/div/div[2]/table/tr/td[2]"))
                )

                actions.context_click(mission_elem_refreshed).perform()

                main_menu = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.dijitMenuPopup")))
                time.sleep(0.5)

                hold_release = main_menu.find_element(By.XPATH, ".//*[contains(text(), 'Hold/Release...')]")
                actions.move_to_element(hold_release).perform()
                time.sleep(1.2)

                click_success = False
                try:
                    hold_targets = browser.find_elements(By.XPATH,
                                                         "//div[contains(@class, 'dijitMenuPopup')]//td[contains(text(), 'Hold...') or text()='Hold...']")
                    for target in hold_targets:
                        if target.is_displayed():
                            target.click()
                            click_success = True
                            break
                except:
                    pass

                if not click_success:
                    js_hold = browser.find_element(By.XPATH, "//td[text()='Hold...' or contains(text(), 'Hold...')]")
                    browser.execute_script("arguments[0].click();", js_hold)

                time.sleep(1.5)

                try:
                    checkbox_xpath = f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[41]/div/div[1]/input"
                    checkbox_elem = wait.until(EC.element_to_be_clickable((By.XPATH, checkbox_xpath)))
                    if not checkbox_elem.is_selected():
                        checkbox_elem.click()

                    time.sleep(0.5)

                    text_input_xpath = f"/html/body/div[2]/div[1]/div[1]/div[{y + 2}]/div[4]/div[42]/div/input"
                    text_input_elem = browser.find_element(By.XPATH, text_input_xpath)
                    text_input_elem.clear()
                    text_input_elem.send_keys("L02")

                    time.sleep(0.5)
                    text_input_elem.send_keys(Keys.RETURN)
                    logger.info("Zatwierdzono procedurę Hold.")

                    time.sleep(1.5)
                except Exception as e_hold:
                    logger.error(f"❌ Błąd w oknie Hold: {e_hold}")
                    ActionChains(browser).send_keys(Keys.ESCAPE).perform()

                logger.info(f"✅ Zakończono pomyślnie wiersz {index + 1}/{len(df)}")

            except Exception as e_row:
                logger.error(f"❌ Błąd wiersza {index + 1}: {e_row}")
                continue  

    except Exception as e_main:
        logger.error(f"Błąd główny pętli: {e_main}")
    finally:
        try:
            change_grade("LNP", x)
        except Exception as e:
            print(f"Błąd przy change_grade: {e}")

def change_grade(client,x):
    global gsheet_csv_url_plan_mte,gsheet_csv_url_plan_lnp,gsheet_csv_url_zlec_mte
    service = EdgeService(executable_path=fr"C:\\Users\\{gv_username}\\Downloads\\msedgedriver.exe")
    browser = webdriver.Edge(service=service, options=browser_configuration())

    browser.implicitly_wait(10)
    #prod
    #browser.get('http://psberfx2.fmlogistic.fr:18080/reflex/logout.jsp')
    #test
    browser.get("http://sgeqrfxap25.fmlogistic.fr:18120/reflex/env/QSBERFX254")
    podsumowanie_msg = f"🤖Robot zaczyna zmieniac grade "
    gChatcopack.wyslij_powiadomienie_do_chata(podsumowanie_msg)
    if client=="LNP":
        alley = "COPA"
        face = "."
        column = x
        level = " "
        lokal = " "
        login = "YIVANO"
        haslo = "YI1234"
        grade="022"
        miscelaos = "201"
        move_reference="copacking"
        Print=True
    try:
        logger.debug("Logowanie")
        browser.find_element(By.XPATH, "/html/body/div/a").click()
        logger.debug("ENTER")
    except:
        pass
    try:
        browser.find_element(By.XPATH, "/html/body/div[4]/div/input[1]").send_keys(login)
        browser.find_element(By.XPATH, "/html/body/div[4]/div/input[2]").send_keys(haslo)
        browser.find_element(By.XPATH, "/html/body/div[4]/div/span").click()
        logger.info("ZALOGOWANO")
    except Exception as e:
        logger.error(f"Blad logowania: {e}")
    try:
        logger.error(f"Nowa sesja: ")
        browser.find_element(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[4]/div[4]/button[2]/div").click()
    except Exception as e:
        logger.error(f"Blad nowej sesji: {e} lub niema potrzeby")
    precyzyjne_zamykanie_skanera(browser)
    try:

        wait = WebDriverWait(browser, 15)

        pick_batches_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[2]/table/tbody/tr/td[2]")))
        pick_batches_button.click()

        print("Przycisk został kliknięty pomyślnie")
    except Exception as e:
        print(f"Błąd podczas wyszukiwania elementu: {e}")
    print("click pick batches", str(datetime.now()))
    time.sleep(5)

    # klick location
    browser.find_element(By.XPATH,
                         f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[1]/div[4]/div/div[3]/span[2]").click()
    #time.sleep(2)
    # alley
    browser.find_element(By.XPATH,
                         f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[7]/div/input").send_keys(
        alley)
    #time.sleep(2)
    # face(.)
    browser.find_element(By.XPATH,
                         f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[8]/div/input").send_keys(
        face)
    # /html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[8]/div/input
    #time.sleep(2)
    # column
    browser.find_element(By.XPATH,
                         f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[9]/div/input").send_keys(
        column)
    time.sleep(2)
    # level
    browser.find_element(By.XPATH,
                         f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[10]/div/input").send_keys(
        level)
    # location
    #time.sleep(2)
    okey = browser.find_element(By.XPATH,
                                f"/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/div[1]/div[3]/div[3]/div/div[11]/div/input")
    okey.send_keys(lokal)
    # enter +enter

    time.sleep(2)
    # ok_button = browser.find_element(By.XPATH, '/html/body/div[2]/div[1]/div[1]/div[8]/div[4]/button[2]/div')

    okey.send_keys(Keys.RETURN, Keys.RETURN)
    print("ty zdes?")
    time.sleep(2)

    print("ili zdes?")

    if client=="LNP":
        time.sleep(2)

        df = get_data_from_gsheet(gsheet_csv_url_plan_lnp)
        if 'sscc' not in df.columns:
            df['sscc'] = ""
        print(df)
        print(df.columns)
        rows_in_reflex = browser.find_elements(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[12]/div[2]/div/div")
        total_rows = len(rows_in_reflex)
        total_rows=total_rows-1
        gChatcopack.wyslij_powiadomienie_do_chata(f"Znaleziono {total_rows} wierszy w tabeli.")

        print(df.columns)
        for x in range(2, total_rows + 1):
            try:
                item_element = browser.find_element(By.XPATH,
                                                    f"/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[12]/div[2]/div/div[{x}]/table/tr/td[2]")
                item_val = item_element.text.strip()

                sscc_element = browser.find_element(By.XPATH,
                                                    f"/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[12]/div[2]/div/div[{x}]/table/tr/td[16]/div/div")
                sscc_val = sscc_element.text.strip()

                gChatcopack.wyslij_powiadomienie_do_chata(f"Przetwarzanie Item: {item_val}, SSCC: {sscc_val}")

                df['Item'] = df['Referencja (Item)'].astype(str).str.strip()

                item_val_str = str(item_val).strip()

                df.loc[df['Item'] == item_val_str, 'sscc'] = sscc_val

                if not df.loc[df['Item'] == item_val_str].empty:
                    gChatcopack.wyslij_powiadomienie_do_chata(f"✅ Sukces! Przypisano SSCC do {item_val_str} w DataFrame.")
                else:
                    gChatcopack.wyslij_powiadomienie_do_chata(
                        f"❌ Błąd! Nie znaleziono {item_val_str} w kolumnie Item. Dostępne wartości: {df['Item'].tolist()}")
                
                actions = ActionChains(browser)
                actions.context_click(item_element).perform()

                wait = WebDriverWait(browser, 10)
                menu_container = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.dijitMenuPopup")))
                modify_option = menu_container.find_element(By.XPATH, ".//td[contains(text(), 'Modify...')]")
                modify_option.click()

                owner_grade_option = wait.until(
                    EC.visibility_of_element_located((By.XPATH, "//td[contains(text(), 'Owner/grade...')]")))
                owner_grade_option.click()

                time.sleep(2)  # Krótkie czekanie na okno

                # miscelaos
                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[19]/div/input").send_keys(
                    miscelaos)
                # grade
                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[15]/div/input").clear()
                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[15]/div/input").send_keys(grade)
                # move reference
                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[22]/div/input").send_keys(
                    move_reference)
                #if Print:
                #    browser.find_element(By.XPATH,
                #                         f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[23]/div/div[1]/input").click()
                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[22]/div/input").send_keys(
                    Keys.ENTER)
                browser.find_element(By.XPATH,
                                     f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[22]/div/input").send_keys(
                    Keys.ENTER)

                
                # Zatwierdzenie (Enter)
                ref_input = browser.find_element(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[22]/div/input")
                ref_input.send_keys(Keys.ENTER)
                time.sleep(1)
                ref_input.send_keys(Keys.ENTER)
                
                print(f"Zakończono wiersz {x}")
                time.sleep(2)  # Skróciłem z 60s dla testów, dostosuj wg potrzeb

            except Exception as e:
                print(f"Błąd w iteracji {x}: {e}")

        
        print(df)
        print(list(df.columns))
        podsumowanie_msg = f"🤖Robot zbiera dane do maperu "
        gChatcopack.wyslij_powiadomienie_do_chata(podsumowanie_msg)
        try:
            nazwa_kolumny_rec = "Numer Recepcji"
            podsumowanie_msg = f"🤖Robot zbiera dane do maperu. Recepcja {str(df[nazwa_kolumny_rec].iloc[0]).strip()}"
            gChatcopack.wyslij_powiadomienie_do_chata(podsumowanie_msg)
            nr_recepcji_czysty = str(df[nazwa_kolumny_rec].iloc[0]).strip()
            with open("wynik_plan.txt", "w", encoding="utf-8") as f:
                f.write(
                    f"HEAD;{nr_recepcji_czysty};L01;{datetime.now().strftime('%Y%m%d')};{nr_recepcji_czysty};COP\n")
                counter = 100
                for index, row in df.iterrows():

                    line = f"LINE;{nr_recepcji_czysty};{counter};{row['Item']};{row['quantity']};{grade};HD{row['sscc']}\n"
                    f.write(line)
                    counter += 100
            print("Plik wynik_plan.txt został wygenerowany.")
        except Exception as e:
            print(f"Błąd zapisu pliku: {e}")
        try:
            #U_kill_chrome.start()
            create_reception("LNP",nr_recepcji_czysty)
        except Exception as e:
            print(f"Błąd mappera: {e}")
    else:
        time.sleep(2)

        df = get_data_from_gsheet(gsheet_csv_url_plan_mte)
        if 'sscc' not in df.columns:
            df['sscc'] = ""
        print(df)
        print(df.columns)
        rows_in_reflex = browser.find_elements(By.XPATH,
                                               "/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[12]/div[2]/div/div")
        total_rows = len(rows_in_reflex)
        total_rows = total_rows - 1
        print(f"Znaleziono {total_rows} wierszy w tabeli.")

        for x in range(2, total_rows + 1):
            grade_path = f"/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[12]/div[2]/div/div[{x}]/table/tr/td[5]/div/div"
            grade_element = wait.until(EC.presence_of_element_located((By.XPATH, grade_path)))
            grade_val = grade_element.text.strip()
            print(grade_val.upper())
            if grade_val.upper() == "022":
                print(f"⏩ Pominięto [{x}]: Grade jest już ustawiony na COP")
                continue
            try:
                wait = WebDriverWait(browser, 15)

                item_path = f"/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[12]/div[2]/div/div[{x}]/table/tr/td[2]"

                item_element = wait.until(EC.presence_of_element_located((By.XPATH, item_path)))
                item_val = item_element.text.strip()

                sscc_path = f"/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[12]/div[2]/div/div[{x}]/table/tr/td[16]"
                sscc_val = browser.find_element(By.XPATH, sscc_path).text.strip()

                print(f"➡️ Przetwarzanie [{x}]: Item: {item_val}, SSCC: {sscc_val}")

                df.loc[df['item_id'] == item_val, 'sscc'] = sscc_val

                actions = ActionChains(browser)
                actions.context_click(item_element).perform()

                menu_container = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.dijitMenuPopup")))
                modify_option = menu_container.find_element(By.XPATH, ".//td[contains(text(), 'Modify...')]")
                modify_option.click()

                owner_grade_option = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//td[contains(text(), 'Owner/grade...')]")))
                owner_grade_option.click()

                misc_input = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[19]/div/input")))
                misc_input.send_keys(miscelaos)

                grade_input = browser.find_element(By.XPATH,
                                                   "/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[15]/div/input")
                grade_input.clear()
                grade_input.send_keys(grade)

                move_ref_input = browser.find_element(By.XPATH,
                                                      "/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[22]/div/input")
                move_ref_input.clear()
                move_ref_input.send_keys(move_reference)

                if Print:
                    browser.find_element(By.XPATH,
                                         "/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[23]/div/div[1]/input").click()

                move_ref_input.send_keys(Keys.ENTER)
                time.sleep(0.5)
                move_ref_input.send_keys(Keys.ENTER)

                wait.until(EC.invisibility_of_element_located((By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[10]")))

                print(f"✅ Zakończono wiersz {x}")
                time.sleep(1)

            except Exception as e:
                print(f"❌ Błąd w iteracji {x}: {e}")
                ActionChains(browser).send_keys(Keys.ESCAPE).perform()

        print(df)
        print(list(df.columns))
    if client=="LNP":
        try:
                nazwa_kolumny_rec = "Numer Recepcji"

                nr_recepcji_czysty = str(df[nazwa_kolumny_rec].iloc[0]).strip()
                with open("wynik_plan_MTE.txt", "w", encoding="utf-8") as f:
                    f.write(
                        f"HEAD;{nr_recepcji_czysty};{datetime.now().strftime('%d.%m.%Y')}\n")
                    counter = 100
                    for index, row in df.iterrows():
                        line = f"BODY;{nr_recepcji_czysty};{counter};{row['item_id']};{row['REQPRT']};{row['quantity']}\n"
                        f.write(line)
                        counter += 100
                print("Plik wynik_plan.txt został wygenerowany.")
        except Exception as e:
                print(f"Błąd zapisu pliku: {e}")
    else:
        try:
            podsumowanie_msg = f"🤖Robot zaczyna zbierac dane do mapera"
            gChatcopack.wyslij_powiadomienie_do_chata(podsumowanie_msg)
            nazwa_kolumny_rec = "Numer Recepcji"

            nr_recepcji_czysty = str(df[nazwa_kolumny_rec].iloc[0]).strip()
            with open("wynik_plan_MTE.txt", "w", encoding="utf-8") as f:
                f.write(
                    f"HEAD;{nr_recepcji_czysty};{datetime.now().strftime('%d.%m.%Y')}\n")
                counter = 100
                row = df.iloc[0]
                line = f"BODY;{nr_recepcji_czysty};{counter};{str(row['REQITM'])[:-1]};{row['REQPRT']};{df["Liczba Stendów"].min()}\n"
                f.write(line)

            print("Plik wynik_plan.txt został wygenerowany.")
        except Exception as e:
            print(f"Błąd zapisu pliku: {e}")
    try:
            #U_kill_chrome.start()

            create_reception(client,nr_recepcji_czysty)
    except Exception as e:
            print(f"Błąd mappera: {e}")
def precyzyjne_zamykanie_skanera(browser):
    print("--- START: Siłowy Reset + Obsługa YES/NO ---")

    def zamknij_okna(browser):
        """Dokładna pętla zamykająca okna od r=12 do 6."""
        r = 15
        while r >= 6:
            try:
                #/html/body/div[2]/div[1]/div[1]/div[12]/div[1]/table/tbody/tr/td[3]/div/span[5]
                btn = browser.find_element(By.XPATH,
                                           f"/html/body/div[2]/div[1]/div[1]/div[{r}]/div[1]/table/tbody/tr/td[3]/div/span[5]")
                print(f"udano r - {r}")
                if btn.is_displayed():
                    btn.click()
                    print("zamyka", r)
                    time.sleep(0.3)
            except:
                print(f"nie udano r - {r}")
            r -= 1
def create_szlecenie(client):
    global gsheet_csv_url_plan_mte,gsheet_csv_url_plan_lnp,gsheet_csv_url_zlec_mte
    #service = Service(executable_path='chromedriver.exe')
    #browser = webdriver.Chrome(service=service, options=browser_configuration())
    service = EdgeService(executable_path=fr"C:\\Users\\{gv_username}\\Downloads\\msedgedriver.exe")
    browser = webdriver.Edge(service=service, options=browser_configuration())
    url_plan = gsheet_csv_url_plan_lnp if client == "LNP" else gsheet_csv_url_plan_mte
    df_expected = get_data_from_gsheet(url_plan)
    browser.implicitly_wait(10)

    try:
        # 1. LOGOWANIE
        #browser.get(TEST_URL)
        browser.get('http://psberfx2.fmlogistic.fr:18080/reflex/logout.jsp')
        time.sleep(2)
        try:
            browser.find_element(By.XPATH, "/html/body/div/a").click()
        except:
            pass

        try:
            browser.find_element(By.XPATH, "/html/body/div[4]/div/input[1]").send_keys("YIVANO")
            browser.find_element(By.XPATH, "/html/body/div[4]/div/input[2]").send_keys("YI1234")
            browser.find_element(By.XPATH, "/html/body/div[4]/div/span").click()
            logger.info("ZALOGOWANO POMYŚLNIE")
        except Exception as e:
            logger.error(f"Błąd logowania: {e}")

        try:
            browser.find_element(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[4]/div[4]/button[2]/div").click()
        except:
            pass

        time.sleep(2)

        precyzyjne_zamykanie_skanera(browser)
        time.sleep(1)

        try:
            pick_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[2]/table/tbody/tr/td[2]")))
            pick_btn.click()
        except:
            browser.find_element(By.XPATH,
                                 "/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[3]/table/tbody/tr/td[2]").click()

        time.sleep(2)

        y = None
        for temp_y in range(6, 16):
            try:
                loc_btn = browser.find_element(By.XPATH,
                                               f"/html/body/div[2]/div[1]/div[1]/div[{temp_y}]/div[4]/div[1]/div[1]/div[4]/div/div[3]/span[2]")
                if loc_btn.is_displayed():
                    loc_btn.click()
                    y = temp_y
                    logger.info(f"Otwarto zakłądkę Location na y={y}")
                    break
            except:
                continue

        if y is None:
            logger.error("❌ Nie znaleziono aktywnego kontenera Location.")
            return

        time.sleep(1)

        browser.find_element(By.XPATH,
                             f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[7]/div/input").send_keys(
            "COPA")
        time.sleep(3)

        browser.find_element(By.XPATH,
                             f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[8]/div/input").send_keys(
            ".")
        time.sleep(3)

        browser.find_element(By.XPATH,
                             f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[9]/div/input").send_keys(
            "RE1")
        time.sleep(3)

        okey = browser.find_element(By.XPATH,
                                    f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[11]/div/input")
        okey.send_keys(Keys.RETURN, Keys.RETURN)

        time.sleep(10)

        row_tables = browser.find_elements(By.XPATH,
                                           f"/html/body/div[2]/div[1]/div[1]/div[{y + 1}]/div[4]/div[12]/div[2]/div/div/table")
        logger.info(f"📦 Znaleziono {len(row_tables)} wierszy w tabeli Reflexa.")

        collected_stock = []
        for r_idx, table_elem in enumerate(row_tables, start=1):
            try:
                item_val = table_elem.find_element(By.XPATH, ".//tr/td[2]").text.strip()
                qty_val = table_elem.find_element(By.XPATH, ".//tr/td[6]").text.strip()

                sscc_val = ""
                try:
                    sscc_val = table_elem.find_element(By.XPATH, ".//tr/td[15]").text.strip()
                    if not sscc_val:
                        sscc_val = table_elem.find_element(By.XPATH, ".//tr/td[16]").text.strip()
                except:
                    pass

                if item_val:
                    collected_stock.append({
                        'item_id': item_val,
                        'quantity': qty_val,
                        'sscc': sscc_val
                    })
            except Exception as e_row:
                logger.warning(f"Błąd odczytu wiersza {r_idx}: {e_row}")

        df_collected = pandas.DataFrame(collected_stock)

        found_ssccs = df_collected['sscc'].tolist() if not df_collected.empty else []
        found_items = df_collected['item_id'].tolist() if not df_collected.empty else []

        df_expected['Status_COPA_RE1'] = df_expected.apply(
            lambda row: "✅ OBECNY" if (row['sscc'] in found_ssccs or row['item_id'] in found_items) else "❌ BRAK",
            axis=1
        )

        print("\n" + "=" * 80)
        print("RAPORT DANYCH ZEBRANYCH NA STREFIE COPA . RE1:")
        print("=" * 80)
        print(df_expected[['item_id', 'sscc', 'alley', 'face', 'przeslo', 'level', 'lokal', 'Status_COPA_RE1']])
        print("=" * 80)

        num_found = (df_expected['Status_COPA_RE1'] == "✅ OBECNY").sum()
        num_missing = (df_expected['Status_COPA_RE1'] == "❌ BRAK").sum()

        logger.info(
            f"🎉 Zakończono zbieranie! Zebrało na COPA.RE1: {num_found}/{len(df_expected)} palet. Brakuje: {num_missing}.")

        return df_expected, df_collected


    except Exception as e_main:
        logger.error(f"Wyjątek główny w collect_stock_copa_re1: {e_main}")
    finally:
        try:
            browser.quit()
        except:
            pass

def create_reception():
    service = EdgeService(executable_path=fr"C:\Users\{gv_username}\Downloads\msedgedriver.exe")
    browser = webdriver.Edge(service=service, options=browser_configuration())
    browser.implicitly_wait(3)
    wait = WebDriverWait(browser, 15)

    try:
        browser.get("http://psberfx2.fmlogistic.fr:18080/reflex/logout.jsp")
        time.sleep(2)

        try:
            logger.debug("Logowanie - kliknięcie Enter")
            browser.find_element(By.XPATH, "/html/body/div/a").click()
        except: pass

        try:
            browser.find_element(By.XPATH, "/html/body/div[4]/div/input[1]").send_keys("YIVANO")
            browser.find_element(By.XPATH, "/html/body/div[4]/div/input[2]").send_keys("YI1234")
            browser.find_element(By.XPATH, "/html/body/div[4]/div/span").click()
            logger.info("ZALOGOWANO POMYŚLNIE")
        except Exception as e:
            logger.error(f"Błąd logowania: {e}")

        try:
            browser.find_element(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[4]/div[4]/button[2]/div").click()
            logger.info("Kliknięto 'Nowa sesja'")
        except Exception as e:
            logger.info(f"Brak okna nowej sesji lub pominięto: {e}")

        time.sleep(2)

        precyzyjne_zamykanie_skanera(browser)
        time.sleep(1)

        try:
            pick_batches_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[3]/table/tbody/tr/td[2]"))#/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[3]/table/tbody/tr/td[2]
            )
            pick_batches_button.click()
            logger.info(f"Kliknięto w przycisk MAPPER w menu {datetime.now()}")
        except Exception as e:
            logger.error(f"Błąd podczas wyszukiwania przycisku w menu: {e}")

        time.sleep(2)

        y = 8
        try:
            browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div/div[3]/div[1]/div/div[2]/div/input").send_keys("MAPPER")
            time.sleep(1)

            okey = browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div/div[3]/div[1]/div/div[7]/div/input")
            okey.send_keys("*LNP_LOD_T")
            time.sleep(1)

            okey.send_keys(Keys.RETURN, Keys.RETURN)
            logger.info("Wprowadzono parametry MAPPER oraz *LNP_LOD_T")
        except Exception as e:
            logger.error(f"Błąd przy wprowadzaniu MAPPER/*LNP+LOD_T na div[{y}]: {e}")

        time.sleep(2)

        try:
            browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[{y+1}]/div[4]/div[3]/div[1]/div[1]/div[2]/table/tbody/tr[1]/td/img").click()
            logger.info("Kliknięto ikonę wgrywania pliku")
        except Exception as e:
            logger.error(f"Błąd kliknięcia ikony wgrywania pliku na div[{y+1}]: {e}")

        time.sleep(2)

        sciezka = fr"C:\Users\{gv_username}\PycharmProjects\SHED\maplnp.txt"
        try:
            send_file = browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[{y+2}]/div[4]/div[8]/input")
            send_file.send_keys(sciezka)
            logger.info(f"Wskazano plik z mapowaniem: {sciezka}")
        except Exception as e:
            logger.error(f"Błąd wprowadzania ścieżki pliku na div[{y+2}]: {e}")
        time.sleep(10)
        browser.find_element(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[3]/div/input").send_keys(
            "MAPPER")
        browser.find_element(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[6]/div/input").send_keys(
            "*LNP_LOD_T")
        time.sleep(4)
        try:
            button_elem = browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/button[3]")
            button_elem.click()
            logger.info("Kliknięto przycisk OK za pomocą standardowego click()")
        except Exception:
            try:
                ok_div = browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/button[3]/div")
                browser.execute_script("arguments[0].click();", ok_div)
                logger.info("Zrealizowano kliknięcie OK przez JavaScript")
            except Exception as e_js:
                logger.warning(f"Próba zatwierdzenia Enterem na aktywnym elemencie: {e_js}")
                browser.switch_to.active_element.send_keys(Keys.RETURN)
                time.sleep(0.5)
                browser.switch_to.active_element.send_keys(Keys.RETURN)
        time.sleep(2)
        mapper = browser.find_element(By.XPATH,
                                      f"/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[2]/div[2]/div/div[2]/table/tr/td[3]/div/div")
        time.sleep(2)
        actions = ActionChains(browser)
        actions.context_click(mapper).perform()

        menu_container = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.dijitMenuPopup"))
        )
        time.sleep(1)

        modify_option = menu_container.find_element(
            By.XPATH, ".//*[contains(text(), 'Incorporate')]"
        )
        modify_option.click()
        logger.info("Kliknięto 'Incorporate / Transmit'")

        status_text = "IIP"
        max_attempts = 12  

        refresh_xpath = f"/html/body/div[2]/div[1]/div[1]/div[{y + 1}]/div[4]/div[3]/div[1]/div[2]/div/table/tbody/tr[1]/td/img"
        status_xpath = (
            f"/html/body/div[2]/div[1]/div[1]/div[{y + 1}]/div[4]//table//tr[1]/td[7]"
        )

        attempt = 0
        while status_text in ["IIP", "TOI", "UNKNOWN"] and attempt < max_attempts:
            attempt += 1
            time.sleep(3)

            try:
                refresh_btn = browser.find_element(By.XPATH, refresh_xpath)
                refresh_btn.click()
                logger.info(
                    f"🔄 Kliknięto ODŚWIEŻ ({attempt}/{max_attempts}). Czekam na wynik..."
                )
            except Exception as e_ref:
                logger.warning(f"Błąd kliknięcia odświeżania: {e_ref}")

            time.sleep(1)

            try:
                status_cell = browser.find_element(By.XPATH, status_xpath)
                status_text = status_cell.text.strip()
            except Exception:
                try:
                    status_cell = browser.find_element(
                        By.XPATH, "//table//tr[1]/td[position()=7]"
                    )
                    status_text = status_cell.text.strip()
                except:
                    status_text = "UNKNOWN"

        if status_text in ["OK", "INC", "FIN"]:
            logger.info(f"✅ SUKCES RECEPCJI! Ostateczny status: {status_text}")
        elif "ERR" in status_text or status_text == "KO":
            logger.error(
                f"❌ BŁĄD PROCESOWANIA W REFLEXIE! Ostateczny status: {status_text}"
            )
        else:
            logger.warning(
                f"⚠️ Przekroczono czas oczekiwania. Zatrzymano na statusie: {status_text}"
            )


    except Exception as e:
        logger.error(f"Wyjątek główny w create_reception: {e}")
    finally:
        # zamknij_wszystkie_okna_do_zera(browser)
        # browser.quit()
        pass
def release_holds_for_order_locations(client="LNP"):
    """Przechodzi po WSZYSTKICH lokalizacjach źródłowych ze zlecenia (z df)

    i wykonuje akcję Release (zdjęcie holda).
    """
    global gsheet_csv_url_plan_lnp, gsheet_csv_url_plan_mte

    url_plan = (
        gsheet_csv_url_plan_lnp if client == "LNP" else gsheet_csv_url_plan_mte
    )
    df = get_data_from_gsheet(url_plan)

    if df is None or df.empty:
        logger.error(
            f"❌ Brak danych w arkuszu dla {client} do wykonania zwalniania holdów."
        )
        return

    df["location_code"] = (
        df["location_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    df["location_code"] = df["location_code"].str.zfill(12)

    df["alley"] = df["location_code"].str[0:4]
    df["face"] = df["location_code"].str[4]
    df["przeslo"] = df["location_code"].str[5:8]
    df["level"] = df["location_code"].str[8:10]
    df["lokal"] = df["location_code"].str[10:13]

    service = EdgeService(
        executable_path=fr"C:\Users\{gv_username}\Downloads\msedgedriver.exe"
    )
    browser = webdriver.Edge(service=service, options=browser_configuration())
    browser.implicitly_wait(3)
    wait = WebDriverWait(browser, 15)

    login = "YIVANO" if client == "LNP" else "NIEROTY MTE"
    haslo = "YI1234" if client == "LNP" else "MTE1234"

    try:
        # 1. LOGOWANIE
        browser.get("http://psberfx2.fmlogistic.fr:18080/reflex/logout.jsp")
        time.sleep(2)
        try:
            browser.find_element(By.XPATH, "/html/body/div/a").click()
        except:
            pass

        browser.find_element(By.XPATH, "/html/body/div[4]/div/input[1]").send_keys(
            login
        )
        browser.find_element(By.XPATH, "/html/body/div[4]/div/input[2]").send_keys(
            haslo
        )
        browser.find_element(By.XPATH, "/html/body/div[4]/div/span").click()
        logger.info("ZALOGOWANO POMYŚLNIE")

        try:
            browser.find_element(
                By.XPATH,
                "/html/body/div[2]/div[1]/div[1]/div[4]/div[4]/button[2]/div",
            ).click()
        except:
            pass

        time.sleep(2)

        # 2. PĘTLA PO KAŻDEJ LOKALIZACJI ZE ZLECENIA (DF)
        for index, row in df.iterrows():
            alley = row["alley"]
            face = row["face"]
            przeslo = row["przeslo"]
            level = row["level"]
            lokal = row["lokal"]
            sscc = row.get("sscc", "-")

            logger.info(
                f"--- 🔓 ANULACJA HOLD DLA WIERSZA {index + 1}/{len(df)} | Adres: {alley}{face}{przeslo}.{level}.{lokal} (SSCC: {sscc}) ---"
            )

            try:
                # Czyszczenie okien przed wyszukaniem nowej lokalizacji
                precyzyjne_zamykanie_skanera(browser)
                time.sleep(1)

                # Otwarte Pick Batches
                try:
                    pick_btn = wait.until(
                        EC.element_to_be_clickable((
                            By.XPATH,
                            "/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[2]/table/tbody/tr/td[2]",
                        ))
                    )
                    pick_btn.click()
                except:
                    browser.find_element(
                        By.XPATH,
                        "/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[3]/table/tbody/tr/td[2]",
                    ).click()

                time.sleep(2)

                # Wyznaczenie Y dla kontenera Location
                y = None
                for temp_y in range(6, 16):
                    try:
                        loc_btn = browser.find_element(
                            By.XPATH,
                            f"/html/body/div[2]/div[1]/div[1]/div[{temp_y}]/div[4]/div[1]/div[1]/div[4]/div/div[3]/span[2]",
                        )
                        if loc_btn.is_displayed():
                            loc_btn.click()
                            y = temp_y
                            break
                    except:
                        continue

                if y is None:
                    logger.error(
                        f"Nie odnaleziono pola Location dla wiersza {index + 1}"
                    )
                    continue

                time.sleep(1)

                # Wpisanie adresu z wiersza zlecenia
                browser.find_element(
                    By.XPATH,
                    f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[7]/div/input",
                ).send_keys(alley)
                browser.find_element(
                    By.XPATH,
                    f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[8]/div/input",
                ).send_keys(face)
                browser.find_element(
                    By.XPATH,
                    f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[9]/div/input",
                ).send_keys(przeslo)
                browser.find_element(
                    By.XPATH,
                    f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[10]/div/input",
                ).send_keys(level)

                okey = browser.find_element(
                    By.XPATH,
                    f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div[1]/div[3]/div[3]/div/div[11]/div/input",
                )
                okey.send_keys(lokal)
                okey.send_keys(Keys.RETURN, Keys.RETURN)

                time.sleep(2)

                # Prawoklik na odnaleziony wiersz palety/misji
                mission_elem = wait.until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        f"/html/body/div[2]/div[1]/div[1]/div[{y+1}]/div[4]/div[12]/div[2]/div/div[2]/table/tr/td[2]",
                    ))
                )

                actions = ActionChains(browser)
                actions.context_click(mission_elem).perform()

                main_menu = wait.until(
                    EC.visibility_of_element_located((
                        By.CSS_SELECTOR,
                        "div.dijitMenuPopup",
                    ))
                )
                time.sleep(0.5)

                hold_release = main_menu.find_element(
                    By.XPATH, ".//*[contains(text(), 'Hold/Release...')]"
                )
                actions.move_to_element(hold_release).perform()
                time.sleep(1.2)

                # Wybór Release... w podmenu
                rel_clicked = False
                try:
                    rel_targets = browser.find_elements(
                        By.XPATH,
                        "//div[contains(@class, 'dijitMenuPopup')]//td[contains(text(),"
                        " 'Release...') or text()='Release...']",
                    )
                    for target in rel_targets:
                        if target.is_displayed():
                            target.click()
                            rel_clicked = True
                            break
                except:
                    pass

                if not rel_clicked:
                    js_rel = browser.find_element(
                        By.XPATH,
                        "//td[text()='Release...' or contains(text(),"
                        " 'Release...')]",
                    )
                    browser.execute_script("arguments[0].click();", js_rel)

                time.sleep(1.5)

                # Potwierdzenie w oknie modalnym (Enter / Confirm)
                try:
                    browser.find_element(
                        By.XPATH,
                        f"/html/body/div[2]/div[1]/div[1]/div[{y+2}]/div[4]/button[9]/div",
                    ).click()
                except:
                    browser.switch_to.active_element.send_keys(Keys.RETURN)

                logger.info(
                    f"✅ Zwolniono Hold (Release) dla lokacji:"
                    f" {alley}{face}{przeslo}.{level}.{lokal}"
                )
                time.sleep(1.5)

            except Exception as e_row:
                logger.error(
                    f"❌ Błąd zwalniania Holda dla wiersza {index + 1}: {e_row}"
                )
                ActionChains(browser).send_keys(Keys.ESCAPE).perform()

        logger.info(
            f"🎉 Zakończono zwalnianie holdów dla wszystkich {len(df)} pozycji ze"
            " zlecenia!"
        )

    except Exception as e:
        logger.error(f"Błąd główny w release_holds_for_order_locations: {e}")
    finally:
        try:
            browser.quit()
        except:
            pass
def create_reception(client, rec_number):
    service = EdgeService(executable_path=fr"C:\Users\{gv_username}\Downloads\msedgedriver.exe")
    browser = webdriver.Edge(service=service, options=browser_configuration())
    browser.implicitly_wait(3)
    wait = WebDriverWait(browser, 15)

    try:
        # 1. LOGOWANIE NA ŚRODOWISKO TESTOWE QSBE
        browser.get('http://sgeqrfxap25.fmlogistic.fr:18120/reflex/env/QSBERFX254')
        time.sleep(2)

        try:
            logger.debug("Logowanie - kliknięcie Enter")
            browser.find_element(By.XPATH, "/html/body/div/a").click()
        except: pass

        try:
            browser.find_element(By.XPATH, "/html/body/div[4]/div/input[1]").send_keys("YIVANO")
            browser.find_element(By.XPATH, "/html/body/div[4]/div/input[2]").send_keys("YI1234")
            browser.find_element(By.XPATH, "/html/body/div[4]/div/span").click()
            logger.info("ZALOGOWANO POMYŚLNIE")
        except Exception as e:
            logger.error(f"Błąd logowania: {e}")

        try:
            browser.find_element(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[4]/div[4]/button[2]/div").click()
            logger.info("Kliknięto 'Nowa sesja'")
        except Exception as e:
            logger.info(f"Brak okna nowej sesji lub pominięto: {e}")

        time.sleep(2)

        # 2. CZYSZCZENIE OKIEN
        precyzyjne_zamykanie_skanera(browser)
        time.sleep(1)

        # 3. OTWARCIE MENU Z MAPPEREM (Pick Batches / Przycisk w menu)
        try:
            # Twój XPATH do przycisku w menu
            pick_batches_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[3]/table/tbody/tr/td[2]"))#/html/body/div[1]/div/div[1]/div[9]/div[1]/div/div[3]/table/tbody/tr/td[2]
            )
            pick_batches_button.click()
            logger.info(f"Kliknięto w przycisk MAPPER w menu {datetime.now()}")
        except Exception as e:
            logger.error(f"Błąd podczas wyszukiwania przycisku w menu: {e}")

        time.sleep(2)

        # 4. WYSZUKANIE MAPPER / *M_REC
        # Wyznaczamy aktywny dywizjon y (domyślnie w twoim kodzie div[8])
        y = 8
        try:
            browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div/div[3]/div[1]/div/div[2]/div/input").send_keys("MAPPER")
            time.sleep(1)

            okey = browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[{y}]/div[4]/div/div[3]/div[1]/div/div[7]/div/input")
            okey.send_keys("*LNP_LOD_T")
            time.sleep(1)

            okey.send_keys(Keys.RETURN, Keys.RETURN)
            logger.info("Wprowadzono parametry MAPPER oraz *LNP_LOD_T")
        except Exception as e:
            logger.error(f"Błąd przy wprowadzaniu MAPPER/*LNP+LOD_T na div[{y}]: {e}")

        time.sleep(2)

        # 5. WEJŚCIE W IKONĘ WYSYŁKI PLIKU (y+1 -> div[9])
        try:
            browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[{y+1}]/div[4]/div[3]/div[1]/div[1]/div[2]/table/tbody/tr[1]/td/img").click()
            logger.info("Kliknięto ikonę wgrywania pliku")
        except Exception as e:
            logger.error(f"Błąd kliknięcia ikony wgrywania pliku na div[{y+1}]: {e}")

        time.sleep(2)

        # 6. WSKAZANIE ŚCIEŻKI DO PLIKU MAPLNP.TXT (y+2 -> div[10])
        sciezka = fr"C:\Users\{gv_username}\PycharmProjects\SHED\wynik_aplan.txt"
        try:
            send_file = browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[{y+2}]/div[4]/div[8]/input")
            send_file.send_keys(sciezka)
            logger.info(f"Wskazano plik z mapowaniem: {sciezka}")
        except Exception as e:
            logger.error(f"Błąd wprowadzania ścieżki pliku na div[{y+2}]: {e}")
        time.sleep(10)
        browser.find_element(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[3]/div/input").send_keys(
            "MAPPER")
        browser.find_element(By.XPATH, "/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/div[6]/div/input").send_keys(
            "*LNP_LOD_T")
        time.sleep(4)
        try:
            # 1. Próba kliknięcia bezpośrednio w guzik BUTTON (zamiast wewnętrznego div)
            button_elem = browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/button[3]")
            button_elem.click()
            logger.info("Kliknięto przycisk OK za pomocą standardowego click()")
        except Exception:
            try:
                # 2. Jeśli coś zasłania element -> KLIKNIĘCIE PRZEZ JAVASCRIPT (nie do zablokowania przez nakładki)
                ok_div = browser.find_element(By.XPATH, f"/html/body/div[2]/div[1]/div[1]/div[10]/div[4]/button[3]/div")
                browser.execute_script("arguments[0].click();", ok_div)
                logger.info("Zrealizowano kliknięcie OK przez JavaScript")
            except Exception as e_js:
                # 3. Awaryjne potwierdzenie ENTERem na aktywnym focusie
                logger.warning(f"Próba zatwierdzenia Enterem na aktywnym elemencie: {e_js}")
                browser.switch_to.active_element.send_keys(Keys.RETURN)
                time.sleep(0.5)
                browser.switch_to.active_element.send_keys(Keys.RETURN)
        time.sleep(2)
        mapper = browser.find_element(By.XPATH,
                                      f"/html/body/div[2]/div[1]/div[1]/div[9]/div[4]/div[2]/div[2]/div/div[2]/table/tr/td[3]/div/div")
        time.sleep(2)
        
        actions = ActionChains(browser)
        actions.context_click(mapper).perform()

        menu_container = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.dijitMenuPopup"))
        )
        time.sleep(1)

        modify_option = menu_container.find_element(
            By.XPATH, ".//*[contains(text(), 'Incorporate')]"
        )
        modify_option.click()
        logger.info("Kliknięto 'Incorporate / Transmit'")

        
        status_text = "IIP"
        max_attempts = 12  

        refresh_xpath = f"/html/body/div[2]/div[1]/div[1]/div[{y + 1}]/div[4]/div[3]/div[1]/div[2]/div/table/tbody/tr[1]/td/img"
        status_xpath = (
            f"/html/body/div[2]/div[1]/div[1]/div[{y + 1}]/div[4]//table//tr[1]/td[7]"
        )

        attempt = 0
        while status_text in ["IIP", "TOI", "UNKNOWN"] and attempt < max_attempts:
            attempt += 1
            time.sleep(3)

            # Klikamy przycisk ODŚWIEŻ
            try:
                refresh_btn = browser.find_element(By.XPATH, refresh_xpath)
                refresh_btn.click()
                logger.info(
                    f"🔄 Kliknięto ODŚWIEŻ ({attempt}/{max_attempts}). Czekam na wynik..."
                )
            except Exception as e_ref:
                logger.warning(f"Błąd kliknięcia odświeżania: {e_ref}")

            time.sleep(1)

            # Odczytujemy aktualny status
            try:
                status_cell = browser.find_element(By.XPATH, status_xpath)
                status_text = status_cell.text.strip()
            except Exception:
                try:
                    status_cell = browser.find_element(
                        By.XPATH, "//table//tr[1]/td[position()=7]"
                    )
                    status_text = status_cell.text.strip()
                except:
                    status_text = "UNKNOWN"

        # 3. FINALNE LOGOWANIE WYNIKU
        if status_text in ["OK", "INC", "FIN"]:
            logger.info(f"✅ SUKCES RECEPCJI! Ostateczny status: {status_text}")
        elif "ERR" in status_text or status_text == "KO":
            logger.error(
                f"❌ BŁĄD PROCESOWANIA W REFLEXIE! Ostateczny status: {status_text}"
            )
            podsumowanie_msg = f"❌ Robot znalazl bląd w maperze!"
            try:
                gChatcopack.wyslij_powiadomienie_do_chata(podsumowanie_msg)
            except:
                pass
        else:
            logger.warning(
                f"⚠️ Przekroczono czas oczekiwania. Zatrzymano na statusie: {status_text}"
            )


    except Exception as e:
        logger.error(f"Wyjątek główny w create_reception: {e}")
    finally:
        # zamknij_wszystkie_okna_do_zera(browser)
        # browser.quit()
        pass

parser = argparse.ArgumentParser(description="Generacja planu")
parser.add_argument("user_id", help="ID uzytkownika")
parser.add_argument("args_json", help="Argumenty w formacie JSON")
args = parser.parse_args()

try:
    user_id = args.user_id
    robot_args = json.loads(args.args_json)
    is_hold_cancel = robot_args.get("anulacjaHold", False)
    action = robot_args.get("action", "")
    target_location = args.get('targetLocation')
    client_name = robot_args.get("client")
    order_number = robot_args.get("orderNumber")
    items_data = robot_args.get("itemsData")

    if client_name == "MTE":
        #main_MTE()
        print(robot_args)
    else:
        logging.info("URUCHOMIONE LNP")
        print(robot_args)
        if "1" in target_location:
            x="RE1"
            main_LNP(x)
        else:
            x="RE2"
            main_LNP(x)
    
    if action == "anulacja_hold" or is_hold_cancel:
        logger.info(f"🔓 Wykryto komendę ANULACJA HOLD dla strefy COPA.{x}. Uruchamiam procedurę Release...")

        
        release_holds_for_order_locations("LNP")

        podsumowanie_msg = f"🔓 Robot pomyślnie zrealizował anulację holdów na strefie COPA.{x} dla zlecenia {order_number}!"
        try:
            gChatcopack.wyslij_powiadomienie_do_chata(podsumowanie_msg)
        except:
            pass

        
    else:
        logger.info("📦 Wykryto komendę REALIZACJA PLANU. Uruchamiam pętlę roboczą...")

        if client_name == "MTE":
            main_MTE()
        else:
            logging.info(f"URUCHOMIONE LNP dla podstrefy {x}")
            main_LNP(x)


except Exception as e:
    print(f"❌ Błąd podczas parsowania argumentów: {e}")


#
#create_zlecenie("LNP","281020250831SAMPLE")


#create_reception()
#main_LNP("RE1")
#change_grade("LNP","RE1")
#create_zlecenie("LNP")

#main_MTE()
#change_grade("MTE")

