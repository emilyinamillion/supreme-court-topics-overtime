"""
Supreme Court Topic Modeling Pipeline
=====================================
A complete pipeline for scraping, processing, and analyzing Supreme Court cases
to extract legal topics using NMF topic modeling.

Based on the original notebook series by [Your Name]
"""

import os
import pandas as pd
import numpy as np
import re
import glob
import json
import requests
from bs4 import BeautifulSoup
import pickle
import time
from pathlib import Path
import logging
from typing import Dict, List, Tuple, Optional
import operator

# NLP and ML imports
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF
from textblob import TextBlob

# Handle different sklearn versions for stop words
try:
    from sklearn.feature_extraction.stop_words import ENGLISH_STOP_WORDS
except ImportError:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Try to import NLTK components (install if needed)
try:
    import nltk
    from nltk.corpus import stopwords, names
    # Download required NLTK data
    nltk.download('stopwords', quiet=True)
    nltk.download('names', quiet=True)
except ImportError:
    print("NLTK not installed. Install with: pip install nltk")
    stopwords = None
    names = None

# Try to import spaCy (install if needed) 
try:
    import spacy
    from spacy.en import English
    parser = English()
except ImportError:
    print("spaCy not installed. Install with: pip install spacy")
    parser = None

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SupremeCourtTopicModeler:
    """
    A complete pipeline for Supreme Court case topic modeling.
    
    Steps:
    1. Scrape case URLs and metadata
    2. Extract full case text
    3. Clean and preprocess text
    4. Apply topic modeling (NMF)
    5. Generate visualization data
    """
    
    def __init__(self, data_dir: str = "data", start_year: int = 1760, end_year: int = 2018):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.start_year = start_year
        self.end_year = end_year
        self.str_data_dir = data_dir
        self.dir_contents = glob.glob(self.str_data_dir)
        
        # Web scraping headers to avoid being blocked
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) \
           Chrome/39.0.2171.95 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # Initialize stopwords
        self._setup_stopwords()
        
        # Results storage
        self.case_urls_df = None
        self.full_cases_df = None
        self.processed_df = None
        self.final_results = None
    
    def _setup_stopwords(self):
        """Set up comprehensive stopwords list for legal text"""
        
        # Basic stopwords
        basic_stopwords = set(ENGLISH_STOP_WORDS)
        if stopwords:
            basic_stopwords.update(stopwords.words('english'))
        
        # Legal/court specific stopwords (reduced list - keep more legal terms)
        legal_stopwords = [
            'join', 'seek', 'note', 'pd', 'misc', 'assistant', 'whereon', 'dismiss', 'sod', 
            'vote', 'present', 'entire', 'ante', 'leave', 'concur', 'entire', 'mootness', 
            'jj', 'amici', 'sup', 'rep', 'stat', 'like', 'rev', 'trans', 'vii', 'erisa', 
            'usca', 'lead', 'cf', 'cca', 'fsupp', 'afdc', 'amicus', 'ante', 'pd', 'aver', 
            'may', 'argued', 'argue', 'decide', 'rptr', 'pp', 'fd', 'june', 'july', 
            'august', 'september', 'october', 'november', 'ca', 'certiorari', 
            'december', 'january', 'february', 'march', 'april', 'writ', 'footnote', 
            'member', 'curiam', 'usc', 'file'
        ]
        
        # Only include most common names to avoid being too aggressive
        if names:
            # Get only very common names to avoid removing too much
            common_male_names = ['john', 'james', 'robert', 'michael', 'william', 'david', 'richard', 'thomas']
            common_female_names = ['mary', 'patricia', 'jennifer', 'linda', 'elizabeth', 'barbara', 'susan', 'jessica']
            all_names = common_male_names + common_female_names
        else:
            all_names = []
        
        # Reduced state names list (only abbreviations to avoid removing content)
        state_abbrevs = [
            'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga', 'hi', 'id', 'il', 'in', 
            'ia', 'ks', 'ky', 'la', 'me', 'md', 'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 
            'nh', 'nj', 'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc', 'sd', 'tn', 
            'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy'
        ]
        
        self.STOPLIST = basic_stopwords.union(set(legal_stopwords + all_names + state_abbrevs))
        logger.info(f"Created stopwords list with {len(self.STOPLIST)} terms")
    
    def beautiful_soup_grabber(self, link: str, max_retries: int = 3) -> BeautifulSoup:
        """
        Get BeautifulSoup object from URL with retry logic
        """
        for attempt in range(max_retries):
            try:
                response = requests.get(link, headers=self.headers, timeout=10)
                response.raise_for_status()
                return BeautifulSoup(response.text, "lxml")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {link}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch {link} after {max_retries} attempts")
                    return None
    
    def step1_get_case_urls(self) -> pd.DataFrame:
        """
        Step 1: Scrape Supreme Court case URLs and metadata
        """
        logger.info("Step 1: Collecting case URLs from Supreme Court archives...")
        
        root_url = "http://caselaw.findlaw.com/court/us-supreme-court/years/"
        years = [root_url + str(year) for year in range(self.start_year, self.end_year + 1)]
        
        case_data = {}
        
        for i, year_url in enumerate(years):
            if i % 10 == 0:
                logger.info(f"Processing year {self.start_year + i}/{self.end_year}")
            
            # Debug: show what URL we're trying to access
            logger.debug(f"Fetching: {year_url}")
            
            soup = self.beautiful_soup_grabber(year_url)
            if not soup:
                logger.warning(f"Failed to get soup for {year_url}")
                continue
            
            # New approach: look for the actual case links in the modern structure
            # Based on the screenshot, cases are in links that go to /us-supreme-court/
            links = soup.findAll("a")
            logger.debug(f"Found {len(links)} total links on {year_url}")
            
            year_case_count = 0
            for link in links:
                href = link.get("href", "")
                
                # New pattern: look for links that contain /us-supreme-court/ and have case numbers
                # Example from screenshot: should match links to actual cases, not years pages
                if href and "/us-supreme-court/" in href and "/years/" not in href:
                    # Additional check: make sure it's not a navigation link
                    if not href.startswith("https://www.findlaw.com/") or "/us-supreme-court/" in href:
                        # Extract case number from URL (last part before .html)
                        url_parts = href.rstrip('/').split('/')
                        if url_parts:
                            last_part = url_parts[-1].replace('.html', '')
                            # Extract numbers for docket
                            docket = re.sub("[^0-9-]", "", last_part)
                            
                            if docket:  # Only add if we found a docket number
                                case_data[href] = docket
                                year_case_count += 1
                                
                                # Debug: show first few matches
                                if year_case_count <= 3:
                                    case_title = link.get_text(strip=True)[:50]
                                    logger.debug(f"  Match {year_case_count}: {href} -> docket {docket} | {case_title}")
            
            logger.info(f"  Year {self.start_year + i}: found {year_case_count} cases")
            
            # Be nice to the server
            time.sleep(0.5)
        
        logger.info(f"Total cases found across all years: {len(case_data)}")
        
        if len(case_data) == 0:
            logger.error("No cases found! Let's examine the page structure more closely...")
            # Let's look at the HTML structure more carefully
            test_year = 2000
            test_url = f"{root_url}{test_year}"
            logger.info(f"Detailed analysis of: {test_url}")
            
            soup = self.beautiful_soup_grabber(test_url)
            if soup:
                # Look for different patterns that might contain case links
                patterns_to_try = [
                    ("Links containing 'supreme'", lambda tag: tag.name == "a" and tag.get("href", "").find("supreme") != -1),
                    ("Links containing case numbers", lambda tag: tag.name == "a" and re.search(r'\d+-\d+', tag.get("href", ""))),
                    ("Links with 'U.S.' in text", lambda tag: tag.name == "a" and "U.S." in tag.get_text()),
                ]
                
                for pattern_name, pattern_func in patterns_to_try:
                    matches = soup.find_all(pattern_func)
                    logger.info(f"\n{pattern_name}: {len(matches)} matches")
                    
                    for j, match in enumerate(matches[:5]):  # Show first 5
                        href = match.get("href", "")
                        text = match.get_text(strip=True)[:80]
                        logger.info(f"  {j+1}. {href} | {text}")
                        
                # Also look at the overall page structure
                logger.info(f"\nPage title: {soup.title.string if soup.title else 'No title'}")
                
                # Look for any div or section that might contain cases
                case_containers = soup.find_all(['div', 'section'], class_=re.compile(r'case|decision|result'))
                logger.info(f"Found {len(case_containers)} potential case containers")
                
        df = pd.DataFrame(list(case_data.items()), columns=["case_url", "docket"])
        
        # Save intermediate result and CSV for inspection
        output_file = self.data_dir / "supcourt_yearlist.pickle"
        csv_file = self.data_dir / "supcourt_yearlist.csv"
        
        df.to_pickle(output_file)
        df.to_csv(csv_file, index=False)
        
        logger.info(f"Step 1 complete. Found {len(df)} cases. Saved to {output_file} and {csv_file}")
        
        self.case_urls_df = df
        return df
    
    def step2_extract_case_text(self, batch_size: int = 5000) -> pd.DataFrame:
        """
        Step 2: Extract full text from each case URL
        """
        logger.info("Step 2: Extracting full case text...")
        
        if self.case_urls_df is None:
            # Try to load from file
            try:
                self.case_urls_df = pd.read_pickle(self.data_dir / "supcourt_yearlist.pickle")
            except FileNotFoundError:
                raise ValueError("No case URLs found. Run step1_get_case_urls() first.")
        
        df = self.case_urls_df.copy()
        
        def extract_case_content(url: str) -> str:
            """Extract case content from a single URL"""
            soup = self.beautiful_soup_grabber(url)
            if not soup:
                return ""
            
            # Try multiple selectors to find case content
            content_selectors = [
                "div.caselawcontent.searchable-content",
                "div.caselawcontent", 
                "div.searchable-content",
                "div[class*='content']",
                "div[class*='case']",
                "div[class*='opinion']",
                "div[class*='text']"
            ]
            
            all_text = []
            
            for selector in content_selectors:
                content_divs = soup.select(selector)
                if content_divs:
                    for div in content_divs:
                        text = div.get_text(separator=' ', strip=True)
                        if text and len(text) > 100:  # Only include substantial text
                            all_text.append(text)
                    break  # Use first successful selector
            
            # Fallback: get all paragraph text if specific selectors fail
            if not all_text:
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 50:  # Only substantial paragraphs
                        all_text.append(text)
            
            # Final fallback: get all text but try to clean it
            if not all_text:
                body_text = soup.get_text(separator=' ', strip=True)
                if len(body_text) > 200:
                    all_text.append(body_text)
            
            result = ' '.join(all_text)
            logger.debug(f"Extracted {len(result)} characters from {url}")
            return result
        
        # Process in batches to avoid overwhelming the server
        total_cases = len(df)
        df['case_text'] = ""
        
        for start_idx in range(0, total_cases, batch_size):
            end_idx = min(start_idx + batch_size, total_cases)
            logger.info(f"Processing cases {start_idx} to {end_idx} of {total_cases}")
            
            batch = df.iloc[start_idx:end_idx].copy()
            batch_results = []
            
            for idx, row in batch.iterrows():
                case_text = extract_case_content(row['case_url'])
                batch_results.append(case_text)
                
                # Progress indicator and rate limiting
                if (idx - start_idx) % 100 == 0:
                    logger.info(f"  Processed {idx - start_idx} cases in current batch")
                time.sleep(0.2)  # Rate limiting
            
            # Update the main dataframe
            df.loc[start_idx:end_idx-1, 'case_text'] = batch_results
            
            # Save intermediate results
            temp_file = self.data_dir / f"temp_batch_{start_idx}_{end_idx}.pickle"
            df.iloc[start_idx:end_idx].to_pickle(temp_file)
        
        # Save final result
        output_file = self.data_dir / "full_proj_preproc.pickle"
        df.to_pickle(output_file)
        logger.info(f"Step 2 complete. Saved to {output_file}")
        
        self.full_cases_df = df
        return df
    
    def tokenize_text(self, text: str) -> List[str]:
        """
        Tokenize and clean text using spaCy if available, otherwise basic processing
        """
        if not text or not isinstance(text, str):
            return []
        
        # Basic cleaning
        separators = ["\xa0\xa0\xa0\xa0", "\r", "\n", "\t", "n't", "'m", "'ll", '[^a-z ]']
        clean_text = text.lower()
        for sep in separators:
            clean_text = re.sub(sep, " ", clean_text)
        
        if parser:
            # Use spaCy for better tokenization and lemmatization
            tokens = parser(clean_text)
            tokens = [tok.lemma_.strip() for tok in tokens if tok.lemma_.strip()]
        else:
            # Fallback to simple tokenization
            tokens = clean_text.split()
        
        # Apply stoplist and length filtering
        final_tokens = [tok for tok in tokens if len(tok) > 1 and tok not in self.STOPLIST]
        
        return final_tokens
    
    def step3_preprocess_text(self) -> pd.DataFrame:
        """
        Step 3: Clean and preprocess case text
        """
        logger.info("Step 3: Preprocessing text...")
        
        if self.full_cases_df is None:
            # Try to load from file
            try:
                self.full_cases_df = pd.read_pickle(self.data_dir / "full_proj_preproc.pickle")
            except FileNotFoundError:
                raise ValueError("No case text found. Run step2_extract_case_text() first.")
        
        df = self.full_cases_df.copy()
        
        # Debug: check text extraction quality
        logger.info("Analyzing extracted text quality...")
        df['text_length'] = df['case_text'].str.len()
        logger.info(f"Text length stats: mean={df['text_length'].mean():.0f}, "
                   f"median={df['text_length'].median():.0f}, "
                   f"min={df['text_length'].min()}, max={df['text_length'].max()}")
        
        # Remove very short documents
        min_length = 200
        initial_count = len(df)
        df = df[df['text_length'] >= min_length]
        logger.info(f"Removed {initial_count - len(df)} documents shorter than {min_length} characters")
        
        if len(df) == 0:
            raise ValueError("No documents remain after filtering short texts. Check text extraction.")
        
        # Sample some documents for debugging
        logger.info("Sample extracted text:")
        for i in range(min(3, len(df))):
            sample_text = df.iloc[i]['case_text'][:200]
            logger.info(f"  Doc {i}: {sample_text}...")
        
        # Apply text preprocessing
        logger.info("Tokenizing and cleaning text...")
        df['processed_text'] = df['case_text'].apply(self.tokenize_text)
        
        # Debug: check tokenization results
        df['token_count'] = df['processed_text'].apply(len)
        logger.info(f"Token count stats: mean={df['token_count'].mean():.0f}, "
                   f"median={df['token_count'].median():.0f}, "
                   f"min={df['token_count'].min()}, max={df['token_count'].max()}")
        
        # Convert back to string for sklearn
        df['processed_text_str'] = df['processed_text'].apply(lambda x: ' '.join(x) if x else '')
        
        # Remove documents with too few tokens
        min_tokens = 10
        initial_count = len(df)
        df = df[df['token_count'] >= min_tokens]
        logger.info(f"Removed {initial_count - len(df)} documents with fewer than {min_tokens} tokens")
        
        if len(df) == 0:
            raise ValueError("No documents remain after tokenization. Check stop words list.")
        
        # Sample processed text for debugging
        logger.info("Sample processed text:")
        for i in range(min(3, len(df))):
            sample_tokens = df.iloc[i]['processed_text'][:20]
            logger.info(f"  Doc {i}: {sample_tokens}")
        
        # Save result
        output_file = self.data_dir / "full_proj_lemmatized.pickle"
        df.to_pickle(output_file)
        logger.info(f"Step 3 complete. {len(df)} documents processed. Saved to {output_file}")
        
        self.processed_df = df
        return df
    
    def step4_topic_modeling(self, n_topics: int = 30, n_top_words: int = 40) -> Tuple[pd.DataFrame, Dict]:
        """
        Step 4: Apply NMF topic modeling
        """
        logger.info("Step 4: Applying topic modeling...")
        
        if self.processed_df is None:
            # Try to load from file
            try:
                self.processed_df = pd.read_pickle(self.data_dir / "full_proj_lemmatized.pickle")
            except FileNotFoundError:
                raise ValueError("No processed text found. Run step3_preprocess_text() first.")
        
        df = self.processed_df.copy()
        
        # Debug vocabulary before TF-IDF
        logger.info("Checking vocabulary before TF-IDF...")
        all_text = ' '.join(df['processed_text_str'].tolist())
        unique_words = set(all_text.split())
        logger.info(f"Total unique words in corpus: {len(unique_words)}")
        
        if len(unique_words) < 100:
            logger.warning(f"Very small vocabulary ({len(unique_words)} words). Reducing min_df.")
            min_df_val = 1
        else:
            min_df_val = 2
        
        # Set up TF-IDF vectorizer with more lenient parameters
        logger.info("Creating TF-IDF vectors...")
        tfidf_vectorizer = TfidfVectorizer(
            max_df=0.95,
            min_df=min_df_val,  # Reduced from 5
            stop_words='english',
            ngram_range=(1, 1),
            max_features=5000  # Limit features to avoid memory issues
        )
        
        try:
            tfidf_matrix = tfidf_vectorizer.fit_transform(df['processed_text_str'])
            feature_names = tfidf_vectorizer.get_feature_names_out()
            logger.info(f"TF-IDF matrix shape: {tfidf_matrix.shape}")
            logger.info(f"Vocabulary size: {len(feature_names)}")
        except ValueError as e:
            logger.error(f"TF-IDF failed: {e}")
            logger.info("Trying with even more lenient parameters...")
            
            # Emergency fallback: very lenient parameters
            tfidf_vectorizer = TfidfVectorizer(
                max_df=0.99,
                min_df=1,
                stop_words=None,  # Don't use sklearn's stop words
                ngram_range=(1, 1),
                max_features=1000
            )
            tfidf_matrix = tfidf_vectorizer.fit_transform(df['processed_text_str'])
            feature_names = tfidf_vectorizer.get_feature_names_out()
            logger.info(f"Fallback TF-IDF matrix shape: {tfidf_matrix.shape}")
        
        # Apply NMF
        logger.info(f"Fitting NMF model with {n_topics} topics...")
        nmf_model = NMF(
            n_components=n_topics,
            random_state=42,
            max_iter=1000
        )
        
        nmf_matrix = nmf_model.fit_transform(tfidf_matrix)
        
        # Assign topics to documents
        topic_assignments = []
        topic_strengths = []
        
        for doc_topics in nmf_matrix:
            max_index, max_value = max(enumerate(doc_topics), key=operator.itemgetter(1))
            topic_assignments.append(max_index)
            topic_strengths.append(max_value)
        
        df['topic_number'] = topic_assignments
        df['topic_strength'] = topic_strengths
        
        # Extract topic words
        topic_words = {}
        for topic_idx, topic in enumerate(nmf_model.components_):
            top_words = [feature_names[i] for i in topic.argsort()[:-n_top_words - 1:-1]]
            topic_words[topic_idx] = ', '.join(top_words)
        
        # Add topic words to dataframe
        df['topic_words'] = df['topic_number'].map(topic_words)
        
        # Print topic summary
        logger.info("\nTopic Summary:")
        topic_counts = df['topic_number'].value_counts().sort_index()
        for topic_idx in range(n_topics):
            count = topic_counts.get(topic_idx, 0)
            words = topic_words[topic_idx][:100] + "..." if len(topic_words[topic_idx]) > 100 else topic_words[topic_idx]
            logger.info(f"Topic {topic_idx} ({count} cases): {words}")
        
        # Save results
        output_file = self.data_dir / "topic_modeled_cases.pickle"
        df.to_pickle(output_file)
        
        # Save topic words separately
        topic_file = self.data_dir / "topic_words.json"
        with open(topic_file, 'w') as f:
            json.dump(topic_words, f, indent=2)
        
        logger.info(f"Step 4 complete. Saved to {output_file}")
        
        self.processed_df = df
        return df, topic_words
    
    def step5_prepare_visualization_data(self) -> pd.DataFrame:
        """
        Step 5: Prepare data for D3.js visualization
        """
        logger.info("Step 5: Preparing visualization data...")
        
        if self.processed_df is None:
            # Try to load from file
            try:
                self.processed_df = pd.read_pickle(self.data_dir / "topic_modeled_cases.pickle")
            except FileNotFoundError:
                raise ValueError("No topic-modeled data found. Run step4_topic_modeling() first.")
        
        df = self.processed_df.copy()
        
        # Extract year from case URL (this might need adjustment based on URL format)
        def extract_year_from_url(url):
            # Try to extract year from URL pattern
            year_match = re.search(r'/(\d{4})/', url)
            if year_match:
                return int(year_match.group(1))
            # Fallback: try to extract from any 4-digit number
            year_match = re.search(r'\b(1[7-9]\d{2}|20[0-2]\d)\b', url)
            if year_match:
                return int(year_match.group(1))
            return None
        
        df['year'] = df['case_url'].apply(extract_year_from_url)
        
        # Remove cases without valid years
        df = df.dropna(subset=['year'])
        df['year'] = df['year'].astype(int)
        
        # Create year-topic counts
        year_topic_counts = df.groupby(['year', 'topic_number']).size().reset_index(name='count')
        
        # Fill missing year-topic combinations with 0
        all_years = range(df['year'].min(), df['year'].max() + 1)
        all_topics = range(df['topic_number'].max() + 1)
        
        # Create complete year-topic grid
        complete_grid = []
        for year in all_years:
            for topic in all_topics:
                complete_grid.append({'year': year, 'topic_number': topic})
        
        complete_df = pd.DataFrame(complete_grid)
        viz_data = complete_df.merge(year_topic_counts, on=['year', 'topic_number'], how='left')
        viz_data['count'] = viz_data['count'].fillna(0).astype(int)
        
        # Add topic metadata (you might want to manually create topic names)
        topic_names = {i: f"Topic {i}" for i in range(df['topic_number'].max() + 1)}
        viz_data['topic_name'] = viz_data['topic_number'].map(topic_names)
        
        # Save visualization data
        viz_file = self.data_dir / "visualization_data.csv"
        viz_data.to_csv(viz_file, index=False)
        
        # Also create yearly totals for brushing visualization
        yearly_totals = df.groupby('year').size().reset_index(name='total_cases')
        yearly_file = self.data_dir / "yearly_totals.csv"
        yearly_totals.to_csv(yearly_file, index=False)
        
        logger.info(f"Step 5 complete. Visualization data saved to {viz_file}")
        
        self.final_results = viz_data
        return viz_data
    
    def get_data(self) -> pd.DataFrame:
        """
        Get the final processed data with topics and case text
        """

        results = {}

        if os.path.exists(self.data_dir / "supcourt_yearlist.pickle"):
            results['case_urls'] = pd.read_pickle(self.data_dir / "supcourt_yearlist.pickle")
        else:
            logger.warning("No case URLs found. Running step1_get_case_urls()...")
            results['case_urls'] = self.step1_get_case_urls()
        if os.path.exists(self.data_dir / "full_proj_preproc.pickle"):
            results['full_cases'] = pd.read_pickle(self.data_dir / "full_proj_preproc.pickle")
        else:
            logger.warning("No full cases found. Running step2_extract_case_text()...")
            results['full_cases'] = self.step2_extract_case_text()
        
        return results

    def run_full_pipeline(self, n_topics: int = 30) -> Dict:
        """
        Run the complete pipeline from start to finish
        """
        logger.info("Starting complete Supreme Court topic modeling pipeline...")
        
        results = {}
        results = self.get_data()
        try:
            
            # Step 3: Preprocess text
            results['processed_cases'] = self.step3_preprocess_text()
            
            # Step 4: Topic modeling
            results['topic_modeled'], results['topic_words'] = self.step4_topic_modeling(n_topics=n_topics)
            
            # Step 5: Prepare visualization data
            results['visualization_data'] = self.step5_prepare_visualization_data()
            
            logger.info("Pipeline completed successfully!")
            # Print summary
            final_df = results['topic_modeled']
            logger.info(f"""
            Pipeline Summary:
            - Total cases processed: {len(final_df)}
            - Number of topics: {n_topics}
            - Data saved to: {self.data_dir}
            """)
            
            return results
            
        except Exception as e:
            logger.error(f"Pipeline failed at step: {e}")
            raise


def main():
    """
    Run the complete Supreme Court topic modeling pipeline
    """
    # Initialize the pipeline with a reasonable range
    pipeline = SupremeCourtTopicModeler(
        data_dir="supreme_court_data",
        start_year=1950,  # Good range for substantial analysis
        end_year=2020
    )
    
    logger.info("Starting complete Supreme Court topic modeling pipeline...")
    logger.info(f"Date range: {1950}-{2020}")
    
    try:
        # Run the complete pipeline
        results = pipeline.run_full_pipeline(n_topics=20)
        
        logger.info("🎉 Pipeline completed successfully!")
        
        # Print final summary
        final_df = results['topic_modeled']
        viz_data = results['visualization_data']
        
        logger.info(f"""
        📊 Final Results Summary:
        ==========================================
        Total cases processed: {len(final_df):,}
        Number of topics identified: {20}
        
        📁 Output files created:
        - supreme_court_data/supcourt_yearlist.csv (case URLs)
        - supreme_court_data/topic_modeled_cases.pickle (full results)
        - supreme_court_data/topic_words.json (topic definitions)
        - supreme_court_data/visualization_data.csv (D3.js ready)
        - supreme_court_data/yearly_totals.csv (for brushing viz)
        
        🏷️  Top 5 Most Common Topics:
        """)
        
        topic_counts = final_df['topic_number'].value_counts().head()
        topic_words_dict = results['topic_words']
         
        for i, (topic_num, count) in enumerate(topic_counts.items()):
            topic_desc = topic_words_dict[topic_num][:80] + "..."
            logger.info(f"  {i+1}. Topic {topic_num}: {count:,} cases")
            logger.info(f"     Keywords: {topic_desc}")
        
        logger.info(f"""
        Next Steps:
        1. Examine topic_words.json to understand the legal topics discovered
        2. Use visualization_data.csv for D3.js time-series visualization
        3. Explore topic_modeled_cases.pickle for detailed analysis
                """)
        
        return results
        
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user. Partial results may be available in the data directory.")
        return None
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        logger.info("Check the data directory for any partial results that were saved.")
        raise


if __name__ == "__main__":
    main()