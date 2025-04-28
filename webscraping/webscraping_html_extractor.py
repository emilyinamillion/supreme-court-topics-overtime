import requests
from requests.exceptions import RequestException, Timeout, HTTPError, TooManyRedirects, ConnectionError
from bs4 import BeautifulSoup
import logging
import time
import urllib.parse
import re
from typing import List, Dict, Union, Optional, Tuple, Any


class GeneralScraper:
    """
    A flexible web scraper for extracting data from websites with robust error handling.
    """
    
    def __init__(self, logger=None, user_agent=None, headers=None, timeout=10):
        """
        Initialize the web scraper with customizable settings.
        
        Args:
            logger: Optional custom logger instance
            user_agent: Optional custom user agent string
            headers: Optional custom HTTP headers dictionary
            timeout: Request timeout in seconds
        """
        # Set up logging
        self.logger = logger or self._setup_default_logger()
        
        # Configure default headers if none provided
        self.timeout = timeout
        default_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        
        # Set up headers
        self.headers = headers or {
            'User-Agent': user_agent or default_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    @staticmethod
    def _setup_default_logger():
        """Create and configure a default logger."""
        logger = logging.getLogger('GeneralScraper')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def fetch_url(self, url: str, max_retries=3, backoff_factor=0.5) -> Optional[requests.Response]:
        """
        Fetch content from a URL with retry mechanism and error handling.
        
        Args:
            url: The URL to fetch
            max_retries: Maximum number of retry attempts
            backoff_factor: Factor to determine exponential backoff between retries
            
        Returns:
            requests.Response or None: The HTTP response or None if all attempts failed
            
        Raises:
            ValueError: If the URL is invalid
            RuntimeError: If all retry attempts fail
        """
        # Validate URL format
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL format: {url}")
        
        attempts = 0
        
        while attempts < max_retries:
            try:
                self.logger.info(f"Attempting to fetch URL: {url} (Attempt {attempts + 1}/{max_retries})")
                
                # Send the HTTP request with a timeout
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()  # Raise exception for bad status codes
                
                # Check if we got a valid HTML response
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' not in content_type.lower():
                    self.logger.warning(f"Expected HTML but got {content_type}")
                
                # Check if response is empty
                if not response.text:
                    raise ValueError("Empty response received")
                
                self.logger.info(f"Successfully fetched URL: {url}")
                return response
                
            except Timeout as e:
                self.logger.warning(f"Request timed out: {e}")
            except ConnectionError as e:
                self.logger.warning(f"Connection error: {e}")
            except HTTPError as e:
                status_code = e.response.status_code if hasattr(e, 'response') else 'unknown'
                self.logger.error(f"HTTP error {status_code}: {e}")
                # Don't retry client errors (4xx)
                if status_code and 400 <= status_code < 500:
                    raise
            except TooManyRedirects as e:
                self.logger.error(f"Too many redirects: {e}")
                raise  # Don't retry redirect issues
            except RequestException as e:
                self.logger.error(f"Request exception: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}", exc_info=True)
                raise  # Don't retry unexpected errors
                
            # Increment attempt counter
            attempts += 1
            
            # If we haven't succeeded and have attempts left, backoff and retry
            if attempts < max_retries:
                wait_time = backoff_factor * (2 ** (attempts - 1))  # Exponential backoff
                self.logger.info(f"Waiting {wait_time:.2f} seconds before retrying...")
                time.sleep(wait_time)
        
        # If we've exhausted all retries
        self.logger.error(f"Failed to fetch URL after {max_retries} attempts: {url}")
        return None
    
    def get_soup(self, url: str, max_retries=3, backoff_factor=0.5, parser='html.parser') -> Optional[BeautifulSoup]:
        """
        Fetch HTML content from a URL and parse it with BeautifulSoup.
        
        Args:
            url: The URL to fetch
            max_retries: Maximum number of retry attempts
            backoff_factor: Factor to determine exponential backoff between retries
            parser: BeautifulSoup parser to use ('html.parser', 'lxml', etc.)
            
        Returns:
            BeautifulSoup or None: Parsed HTML content or None if fetching failed
            
        Raises:
            ValueError: If the URL is invalid
            RuntimeError: If all retry attempts fail
        """
        response = self.fetch_url(url, max_retries, backoff_factor)
        
        if response is None:
            return None
        
        try:
            soup = BeautifulSoup(response.text, parser)
            
            # Simple validation that we got meaningful content
            if not soup.find('body'):
                self.logger.warning("No <body> tag found in the HTML")
            
            self.logger.info(f"Successfully parsed HTML from URL: {url}")
            return soup
            
        except Exception as e:
            self.logger.error(f"Error parsing HTML content: {e}", exc_info=True)
            return None
    
    def extract_links(self, url: str, filter_pattern=None, keep_link_text=False, 
                     css_selector='a', attribute='href') -> List[Union[str, Tuple[str, str]]]:
        """
        Extract links from a webpage with customizable selectors and filters.
        
        Args:
            url: The URL of the webpage to scrape
            filter_pattern: Optional string pattern to filter URLs
            keep_link_text: If True, return tuples of (url, link_text) 
            css_selector: CSS selector to find link elements
            attribute: HTML attribute containing the URL
            
        Returns:
            List of URLs or (URL, link_text) tuples if keep_link_text is True
        """
        soup = self.get_soup(url)
        
        if soup is None:
            return []
        
        try:
            # Find all matching elements and extract the specified attribute
            results = []
            for element in soup.select(css_selector):
                if element.has_attr(attribute):
                    href = element[attribute]
                    
                    # Handle relative URLs
                    if href and not href.startswith(('http://', 'https://', 'mailto:', 'tel:')):
                        href = urllib.parse.urljoin(url, href)
                    
                    # Apply filtering if needed
                    if not filter_pattern or filter_pattern in href:
                        if keep_link_text:
                            # Get the text content of the element
                            element_text = element.get_text(strip=True)
                            # If no text, use the URL as text
                            if not element_text:
                                element_text = href
                            results.append((href, element_text))
                        else:
                            results.append(href)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error extracting links: {e}")
            return []
    
    def extract_elements(self, soup: BeautifulSoup, css_selector: str, 
                       extract_attrs=None) -> List[Dict[str, Any]]:
        """
        Extract elements from a BeautifulSoup object using CSS selectors.
        
        Args:
            soup: BeautifulSoup object
            css_selector: CSS selector string to find elements
            extract_attrs: Optional list of attributes to extract from each element
            
        Returns:
            List of dictionaries containing element data
        """
        if not isinstance(soup, BeautifulSoup):
            raise TypeError(f"Expected BeautifulSoup object, got {type(soup)}")
        
        results = []
        try:
            elements = soup.select(css_selector)
            
            for i, element in enumerate(elements):
                # Create an item with the element text
                item = {
                    'text': element.get_text(strip=True),
                    'element_type': element.name,
                    'location': f"{element.name}-{i}"
                }
                
                # Extract requested attributes
                if extract_attrs:
                    for attr in extract_attrs:
                        if element.has_attr(attr):
                            item[attr] = element[attr]
                
                # Only add non-empty elements
                if item['text']:
                    results.append(item)
                    
            return results
            
        except Exception as e:
            self.logger.error(f"Error extracting elements: {e}")
            return []
    
    def extract_structured_data(self, url: str, extraction_config: Dict) -> Dict[str, Any]:
        """
        Extract structured data from a webpage using a configuration dictionary.
        
        Args:
            url: The URL to scrape
            extraction_config: Dictionary defining what data to extract and how
            
        Returns:
            Dictionary of extracted data
        """
        soup = self.get_soup(url)
        
        if soup is None:
            return {'error': 'Failed to fetch URL', 'url': url}
        
        result = {}
        
        try:
            for section_name, config in extraction_config.items():
                section_type = config.get('type', 'elements')
                
                if section_type == 'elements':
                    # Extract elements using CSS selectors
                    selector = config.get('selector', '')
                    attributes = config.get('attributes', [])
                    
                    if selector:
                        result[section_name] = self.extract_elements(soup, selector, attributes)
                        
                elif section_type == 'text':
                    # Extract text from a selector
                    selector = config.get('selector', '')
                    
                    if selector:
                        elements = soup.select(selector)
                        if elements:
                            result[section_name] = elements[0].get_text(strip=True)
                
                elif section_type == 'attribute':
                    # Extract an attribute value from a selector
                    selector = config.get('selector', '')
                    attribute = config.get('attribute', '')
                    
                    if selector and attribute:
                        elements = soup.select(selector)
                        if elements and elements[0].has_attr(attribute):
                            result[section_name] = elements[0][attribute]
                
                elif section_type == 'regex':
                    # Extract data using regex pattern
                    selector = config.get('selector', '')
                    pattern = config.get('pattern', '')
                    
                    if selector and pattern:
                        elements = soup.select(selector)
                        if elements:
                            text = elements[0].get_text()
                            matches = re.search(pattern, text)
                            if matches:
                                result[section_name] = matches.group(1) if matches.groups() else matches.group(0)
                                
                elif section_type == 'custom':
                    # Use a custom function for extraction
                    custom_func = config.get('function')
                    if custom_func and callable(custom_func):
                        result[section_name] = custom_func(soup)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error extracting structured data: {e}", exc_info=True)
            return {'error': str(e), 'url': url}


# Example subclass for specific website scraping
class CourtCaseScraper(GeneralScraper):
    """
    Specialized scraper for court case websites.
    """
    
    def parse_case_page(self, url: str) -> Dict[str, Any]:
        """
        Parse a court case webpage and extract structured information.
        
        Args:
            url: URL of the court case page
            
        Returns:
            Dictionary containing structured information about the case
        """
        soup = self.get_soup(url)
        
        if soup is None:
            return {'error': 'Failed to fetch URL', 'url': url}
        
        # Define the extraction configuration
        case_config = {
            'case_info': {
                'type': 'custom',
                'function': self._extract_case_info
            },
            'header_text': {
                'type': 'elements',
                'selector': 'h2, strong.heading, span.headertext'
            },
            'case_text': {
                'type': 'elements',
                'selector': 'div.content p, div.text-left p, div.block p'
            },
            'opinions': {
                'type': 'elements',
                'selector': 'div[id^="tab-opinion-"] p, div.opinion p'
            },
            'footnotes': {
                'type': 'elements',
                'selector': 'p a[name^="F"], p a[name*="foot"]'
            }
        }
        
        # Use the generic extraction method with our specialized config
        results = self.extract_structured_data(url, case_config)
        
        # Post-processing
        if 'case_text' in results and isinstance(results['case_text'], list):
            results['case_text'] = self._filter_case_text(results['case_text'])
        
        if 'opinions' in results and isinstance(results['opinions'], list):
            results['opinions'] = self._filter_opinions(results['opinions'])
        
        return results
    
    def _extract_case_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Custom function to extract case information."""
        case_info = {}
        
        # Extract court info and case title
        headers = soup.select('h2, strong, span')
        for header in headers:
            text = header.get_text().strip()
            if "Supreme Court" in text:
                case_info['court'] = text
            elif " v. " in text:
                case_info['title'] = text
                # Try to extract citation
                citation_match = re.search(r'\d+\s+U\.S\.\s+\d+\s+\(\d+\)', text)
                if citation_match:
                    case_info['citation'] = citation_match.group(0)
        
        # Extract case date
        date_pattern = r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b'
        for element in soup.select('h2, p, div.content'):
            text = element.get_text().strip()
            matches = re.findall(date_pattern, text)
            if matches:
                case_info['date'] = matches[0]
                break
        
        # Extract external links
        search_section = soup.find('div', class_='search-case')
        if search_section:
            links = search_section.find_all('a')
            case_info['external_links'] = []
            
            for link in links:
                link_text = link.get_text().strip() 
                if link_text:
                    case_info['external_links'].append({
                        'text': link_text,
                        'url': link.get('href', ''),
                        'title': link.get('title', '')
                    })
        
        return case_info
    
    def _filter_case_text(self, case_text: List[Dict]) -> List[Dict]:
        """Filter and deduplicate case text paragraphs."""
        seen_texts = set()
        filtered_text = []
        
        for item in case_text:
            text = item['text']
            # Normalize text for comparison
            norm_text = ' '.join(text.lower().split())
            
            # Skip short or navigation paragraphs
            if (len(norm_text) <= 20 or 
                any(nav_term in norm_text for nav_term in ['next page', 'previous page', 'google'])):
                continue
            
            # Skip duplicates
            if norm_text not in seen_texts:
                seen_texts.add(norm_text)
                filtered_text.append(item)
        
        return filtered_text
    
    def _filter_opinions(self, opinions: List[Dict]) -> List[Dict]:
        """Filter and deduplicate opinion paragraphs."""
        seen_texts = set()
        filtered_opinions = []
        
        for item in opinions:
            text = item['text']
            # Normalize text for comparison
            norm_text = ' '.join(text.lower().split())
            
            # Skip short fragments
            if len(norm_text) <= 20:
                continue
            
            # Skip duplicates
            if norm_text not in seen_texts:
                seen_texts.add(norm_text)
                filtered_opinions.append(item)
        
        return filtered_opinions


# Example usage
if __name__ == "__main__":
    # Basic scraper usage
    scraper = GeneralScraper()
    soup = scraper.get_soup("https://example.com")
    if soup:
        # Get all links from the page
        links = scraper.extract_links("https://example.com")
        print(f"Found {len(links)} links")
        
        # Extract elements using CSS selectors
        headings = scraper.extract_elements(soup, "h1, h2, h3")
        print(f"Found {len(headings)} headings")
    
    # Specialized court case scraper
    court_scraper = CourtCaseScraper()
    case_data = court_scraper.parse_case_page("https://example.com/supreme_court_case")
    print(f"Extracted case data: {list(case_data.keys())}")