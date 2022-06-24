from bs4 import BeautifulSoup
import requests
import re

import pandas as pd
import numpy as np

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) \
           Chrome/39.0.2171.95 Safari/537.36'}


root_url = "http://caselaw.findlaw.com/court/us-supreme-court/years/"

years = [root_url + str(year) for year in range(1760, 2018)]


def Beautiful_soup_grabber(link):
    response = requests.get(link, headers=headers)
    return BeautifulSoup(response.text, "lxml")


def year_getter(years):
    y = {}
    for year in years:
        soup = Beautiful_soup_grabber(year)
        souplist = soup.findAll("a")
        for i in souplist:
            if re.search("us-supreme-court", str(i)) and not re.search("years", str(i)) and not re.search("/court/",
                                                                                                          str(i)):
                b = i["href"]
                y[b] = [re.sub("[^0-9]", "", b.split("/")[-1])]
    return pd.DataFrame(y).transpose().reset_index()

if __name__ == '__main__':
    df = year_getter(years)
    df.columns = ["case_url", "docket"]
    df.to_pickle("supcourt_yearlist.pickle")