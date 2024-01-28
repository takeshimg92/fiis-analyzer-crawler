import numpy as np
import locale
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)

import pandas as pd

pd.options.display.max_columns = None
pd.options.mode.chained_assignment = None  # default='warn'

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scipy.special import expit as sigmoid


def create_driver(debugging=False):
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    chrome_options = Options()
    if not debugging:
        chrome_options.add_argument("start-maximized")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless")

    return webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=chrome_options
    )


def read_raw_fiis_table(debug=False):
    print("Running crawler (takes about 1 minute)")

    from time import sleep

    try:
        print("Creating Selenium driver...")
        driver = create_driver(debugging=debug)

        print("Accessing page...")
        driver.get("https://www.fundsexplorer.com.br/ranking")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@id='colunas-ranking__select-button']")
            )
        )

        print("Ensuring all columns are available...")
        driver.execute_script("window.scrollTo(0, 200)")
        driver.find_element(
            By.XPATH, "//div[@id='colunas-ranking__select-button']"
        ).click()  # open drop-down menu

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//label[@for='colunas-ranking__todos']")
            )
        )
        driver.find_element(
            By.XPATH, "//label[@for='colunas-ranking__todos']"
        ).click()  # makes all columns available
        sleep(5)

        print("Table found. Loading...")
        table = driver.find_element(By.CLASS_NAME, "default-fiis-table__container")
        df = pd.read_html("<table>" + table.get_attribute("outerHTML") + "</table>")[0]
        return df

    finally:
        print("Quitting driver...")
        driver.quit()


def process_money(x, normalize_fractions=True):
    try:
        y = locale.atof(str(x))
        if ("," not in str(x)) and normalize_fractions:
            y = y / 100
        return y
    except ValueError:
        return np.nan


def process_fiis_table(fiis, normalize_fractions=True):
    fiis = fiis.dropna(axis=1, how="all")  # remove columns which are full NA
    fiis.columns = (
        fiis.columns.str.strip()
        .str.replace(" ", "_")
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
    )

    fiis = fiis.dropna(
        subset=[
            "preco_atual_(r$)",
            "liquidez_diaria_(r$)",
            "p/vp",
            "p/vpa",
            "ultimo_dividendo",
            "dividend_yield",
        ]
    )  # I don't care fore weird funds which are either too new or too complex

    money_columns = ["liquidez_diaria_(r$)", "p/vp", "p/vpa", "volatilidade"]

    percent_columns = [
        "dividend_yield",
        "dy_(3m)_acumulado",
        "dy_(6m)_acumulado",
        "dy_(12m)_acumulado",
        "dy_(3m)_media",
        "dy_(6m)_media",
        "dy_(12m)_media",
        "dy_ano",
        "variacao_preco",
        "rentab._periodo",
        "rentab._acumulada",
        "dy_patrimonial",
        "variacao_patrimonial",
        "rentab._patr._periodo",
        "rentab._patr._acumulada",
    ]

    number_cols = [
        "num._cotistas",
        "preco_atual_(r$)",
        "ultimo_dividendo",
        "patrimonio_liquido",
        "vpa",
    ]

    for col in percent_columns:
        fiis[col] = fiis[col].str.split(" %").str[0].apply(process_money)

    for col in number_cols:
        fiis[col] = fiis[col].apply(
            lambda x: process_money(x, normalize_fractions=False)
        )

    for col in money_columns:
        fiis[col] = fiis[col].apply(process_money)

    fiis["p/vpa"] = fiis["p/vpa"] / 10.0
    fiis["preco_atual_(r$)"] = fiis["preco_atual_(r$)"] / 100.0
    fiis["vpa"] = fiis["vpa"] / 100.0

    return fiis


def get_vacancies():
    import requests

    url = "https://www.meusdividendos.com/fundos-imobiliarios/vacancias"
    response = requests.get(url)
    html_content = response.text
    df = pd.read_html(html_content, attrs={"id": "tabela-fundos"})[0]
    df["fundos"] = df["Fundo"] + "11"
    df = df.drop(["Fundo", "#"], axis=1)
    df.columns = (
        df.columns.str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
    )
    return df


def filter_per_quantile(df, column, percentile, keep="larger"):
    assert keep in ("larger", "smaller")
    q = df[column].quantile(percentile)
    match keep:
        case "larger":
            return df[df[column] >= q]
        case "smaller":
            return df[df[column] <= q]
        case _:
            raise


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "pt_BR.UTF-8")

    df = read_raw_fiis_table(debug=False)
    # since a few years back, fundsexplorer doesn't provide vacancy information anymore
    vac = get_vacancies()

    setores_to_keep = [
        "Indefinido",
        "Papéis",
        "Fundo de Fundos",
        "Misto",
        "Imóveis Residenciais",
        "Imóveis Industriais e Logísticos",
        "Agências de Bancos",
        "Imóveis Comerciais - Outros",
        "Varejo",
    ]

    # processa e limpa, e inclui vacancias
    fiis = process_fiis_table(df)
    fiis = fiis.merge(vac, on="fundos", how="left")

    # basic cleanup -- CHOOSE WHATEVER FILTERS YOU LIKE
    fiis = fiis[fiis["patrimonio_liquido"] > 0]
    fiis = fiis[fiis["p/vp"] < 10]  # remove outliers
    fiis = fiis[fiis["num._cotistas"] > 0]
    fiis = fiis[fiis["dy_(12m)_media"] > 0]  # keep funds which are at least 1 year old

    # investment choices -- CHOOSE WHATEVER FILTERS YOU LIKE
    fiis = fiis[fiis["setor"].isin(setores_to_keep)]  # lower-risk
    fiis = fiis[(fiis["vacancia"] < 0.25) | fiis["vacancia"].isna()]  # lower-risk
    fiis = fiis[(fiis["p/vpa"] >= 0.9) & (fiis["p/vpa"] < 1.1)]  # reasonable prices
    fiis = filter_per_quantile(
        fiis, "patrimonio_liquido", 0.25, keep="larger"
    )  # preferir patrimonio liquido razoavel
    fiis = filter_per_quantile(
        fiis, "dy_(12m)_acumulado", 0.50, keep="larger"
    )  # preferir performance alta historica
    fiis = filter_per_quantile(
        fiis, "num._cotistas", 0.25, keep="larger"
    )  # preferir numero razoavel de cotistas
    fiis = filter_per_quantile(
        fiis, "liquidez_diaria_(r$)", 0.25, keep="larger"
    )  # preferir alta liquidez
    fiis = filter_per_quantile(
        fiis, "volatilidade", 0.8, keep="smaller"
    )  # manter volatilidade relativamente baixa

    # building score
    fiis["p_dy"] = fiis["dy_(12m)_acumulado"].rank(pct=True)
    fiis["p_vol"] = fiis["volatilidade"].rank(pct=True)
    fiis["sig"] = sigmoid(20 * (1 - fiis["p/vpa"]))

    a, b, c = 50, 15, 35
    fiis["score"] = (
        a * fiis["p_dy"] + b * (1 - fiis["p_vol"]) + c * fiis["sig"]
    ).astype(int)
    date = pd.to_datetime("now").strftime("%Y-%m-%d")

    # saving to file
    filename = f"fundos_imobiliarios_{date}.xlsx"
    fiis.sort_values("score", ascending=False).to_excel(filename, index=False)
    print(f"Table saved to {filename}!")
