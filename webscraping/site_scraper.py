"""
This is a metaflow pipeline for collecting data on supreme court cases from a specific website.
The pipeline runs collection for all years in parallel which speeds up the process rapidly.
to run this file open a terminal and enter (keeping in mind file/path/to in your own env):
    python site_scraper.py run --max-num-splits 500

More on the metaflow library:
https://docs.metaflow.org/metaflow/basics

Run the following to view the pipeline graph
python site_scraper.py show

"""

from metaflow import FlowSpec, IncludeFile, step
from bs4 import BeautifulSoup
import requests
import re
from datetime import datetime
import pandas as pd
import numpy as np


def Beautiful_soup_grabber(link):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) \
                       Chrome/39.0.2171.95 Safari/537.36'}
    response = requests.get(link, headers=headers)
    return BeautifulSoup(response.text, "lxml")



class ScrapeDataFlow(FlowSpec):

    @step
    def start(self):
        """
        setup
        """
        self.this_year = datetime.now().year
        self.root_url = "http://caselaw.findlaw.com/court/us-supreme-court/years/"
        year_gen = range(1760, self.this_year + 1)
        self.link_list = [(y,f"{self.root_url}{str(y)}") for y in year_gen]
        #self.link_list = self.root_url + str(year) for year in range(1760, self.this_year + 1)]
        self.next(self.get_urls_for_cases_in_year, foreach = "link_list")


    @step
    def get_urls_for_cases_in_year(self):
        """
        metaflow has a special format for parallelizing a for loop. though
        self.input is not defined above, it exists in this function as an item
        designated by foreach = "link_list"
        """
        year, url = self.input
        year_dict = {}
        soup = Beautiful_soup_grabber(url)
        souplist = soup.findAll("a")
        for i in souplist:
            if re.search("us-supreme-court", str(i)) and not re.search("years", str(i)) and not re.search("/court/",
                                                                                                          str(i)):
                b = i["href"]
                year_dict[b] = [re.sub("[^0-9]", "", b.split("/")[-1]), year]

        self.df = pd.DataFrame(year_dict).transpose()
        print(f"{year} produced {len(self.df)} cases")
        self.next(self.join_year_url_dfs)

    @step
    def join_year_url_dfs(self, inputs):
        """
        A join step to bring together all dataframes created in the previous step.
        """
        self.results = pd.concat([input.df for input in inputs]).reset_index()
        self.results.columns = ["case_url", "docket", "year"]
        self.next(self.end)

    @step
    def end(self):
        """
        an end step
        """
        self.results.to_pickle("supreme_court_year_url_list.pickle")


if __name__ == '__main__':
    ScrapeDataFlow()
