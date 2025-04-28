import unittest
from unittest.mock import patch, MagicMock, call
import requests
from bs4 import BeautifulSoup
import logging
import io
import re
import sys
import os

# Add the parent directory to sys.path to allow importing the module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webscraping_html_extractor import GeneralScraper, CourtCaseScraper


class TestGeneralScraper(unittest.TestCase):
    """Test cases for the GeneralScraper class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a test logger that writes to a string buffer
        self.log_capture = io.StringIO()
        handler = logging.StreamHandler(self.log_capture)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        
        self.test_logger = logging.getLogger('test_logger')
        self.test_logger.setLevel(logging.INFO)
        for h in self.test_logger.handlers:
            self.test_logger.removeHandler(h)
        self.test_logger.addHandler(handler)
        
        # Create a scraper instance with our test logger
        self.scraper = GeneralScraper(logger=self.test_logger)
        
        # Sample HTML content for testing
        self.sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
        </head>
        <body>
            <h1 class="main-title">Main Title</h1>
            <div class="content">
                <p>First paragraph with <a href="https://example.com/link1">Link 1</a></p>
                <p>Second paragraph</p>
                <h2 id="section1">Section 1</h2>
                <p>Section 1 content</p>
                <ul class="links">
                    <li><a href="https://example.com/link2" class="external">Link 2</a></li>
                    <li><a href="/relative/link3">Link 3</a></li>
                    <li><a href="https://example.com/link4">Link 4</a></li>
                </ul>
                <div class="product" id="product1" data-price="19.99">
                    <h3>Product Title</h3>
                    <span class="price">$19.99</span>
                    <img src="/images/product.jpg" alt="Product Image" />
                </div>
            </div>
        </body>
        </html>
        """
        self.sample_soup = BeautifulSoup(self.sample_html, 'html.parser')
    
    def tearDown(self):
        """Clean up after each test method."""
        handlers = self.test_logger.handlers[:]
        for handler in handlers:
            self.test_logger.removeHandler(handler)
            handler.close()
    
    def test_init_default_logger(self):
        """Test that the default logger is created correctly."""
        scraper = GeneralScraper()
        self.assertIsNotNone(scraper.logger)
        self.assertEqual(scraper.logger.name, 'GeneralScraper')
    
    def test_init_custom_logger(self):
        """Test that a custom logger can be provided."""
        self.assertEqual(self.scraper.logger, self.test_logger)
    
    def test_init_custom_headers(self):
        """Test that custom headers can be provided."""
        custom_headers = {'User-Agent': 'Custom/1.0', 'X-Test': 'Test'}
        scraper = GeneralScraper(headers=custom_headers)
        self.assertEqual(scraper.headers, custom_headers)
    
    def test_init_custom_user_agent(self):
        """Test that a custom user agent can be provided."""
        custom_user_agent = 'CustomBot/1.0'
        scraper = GeneralScraper(user_agent=custom_user_agent)
        self.assertEqual(scraper.headers['User-Agent'], custom_user_agent)
    
    @patch('requests.get')
    def test_fetch_url_success(self, mock_get):
        """Test successful URL fetching."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.text = self.sample_html
        mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        mock_get.return_value = mock_response
        
        # Call the method
        result = self.scraper.fetch_url('https://example.com')
        
        # Verify the result
        self.assertEqual(result, mock_response)
        mock_get.assert_called_once_with(
            'https://example.com',
            headers=self.scraper.headers,
            timeout=self.scraper.timeout
        )
    
    @patch('requests.get')
    def test_fetch_url_invalid_url(self, mock_get):
        """Test that an invalid URL raises ValueError."""
        with self.assertRaises(ValueError):
            self.scraper.fetch_url('invalid-url')
        
        mock_get.assert_not_called()
    
    @patch('requests.get')
    def test_fetch_url_empty_response(self, mock_get):
        """Test handling of empty response."""
        # Configure mock for empty response
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        mock_get.return_value = mock_response
        
        # First call succeeds but raises ValueError for empty content
        mock_get.side_effect = [mock_response]
        
        # Call the method
        with self.assertRaises(ValueError):
            self.scraper.fetch_url('https://example.com', max_retries=1)
        
        # Verify that the error was logged
        self.assertIn('Empty response received', self.log_capture.getvalue())
    
    @patch('requests.get')
    def test_fetch_url_timeout(self, mock_get):
        """Test handling of timeout errors with retries."""
        # Configure mock to raise Timeout twice then succeed
        mock_response = MagicMock()
        mock_response.text = self.sample_html
        mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        
        mock_get.side_effect = [
            requests.exceptions.Timeout("Connection timed out"),
            requests.exceptions.Timeout("Connection timed out"),
            mock_response
        ]
        
        # Call the method with 3 max retries
        result = self.scraper.fetch_url('https://example.com', max_retries=3, backoff_factor=0.1)
        
        # Verify the result
        self.assertEqual(result, mock_response)
        self.assertEqual(mock_get.call_count, 3)
        
        # Verify that timeouts were logged
        log_output = self.log_capture.getvalue()
        self.assertIn('Request timed out', log_output)
        self.assertIn('Waiting', log_output)
    
    @patch('requests.get')
    def test_fetch_url_max_retries_exceeded(self, mock_get):
        """Test that max retries exceeded returns None."""
        # Configure mock to always raise Timeout
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        # Call the method with 3 max retries
        result = self.scraper.fetch_url('https://example.com', max_retries=3, backoff_factor=0.1)
        
        # Verify the result
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, 3)
        
        # Verify that failure was logged
        self.assertIn('Failed to fetch URL after 3 attempts', self.log_capture.getvalue())
    
    @patch('requests.get')
    def test_fetch_url_http_client_error(self, mock_get):
        """Test that HTTP client errors (4xx) are not retried."""
        # Configure mock to raise HTTPError with a 404 status code
        response = MagicMock()
        response.status_code = 404
        error = requests.exceptions.HTTPError("404 Client Error", response=response)
        mock_get.side_effect = error
        
        # Call the method
        with self.assertRaises(requests.exceptions.HTTPError):
            self.scraper.fetch_url('https://example.com', max_retries=3)
        
        # Verify that it only tried once and didn't retry
        self.assertEqual(mock_get.call_count, 1)
        
        # Verify that error was logged
        self.assertIn('HTTP error 404', self.log_capture.getvalue())
    
    @patch('requests.get')
    def test_fetch_url_http_server_error(self, mock_get):
        """Test that HTTP server errors (5xx) are retried."""
        # Configure mock to raise HTTPError twice with 500, then succeed
        response1 = MagicMock()
        response1.status_code = 500
        error1 = requests.exceptions.HTTPError("500 Server Error", response=response1)
        
        response2 = MagicMock()
        response2.status_code = 500
        error2 = requests.exceptions.HTTPError("500 Server Error", response=response2)
        
        mock_response = MagicMock()
        mock_response.text = self.sample_html
        mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        
        mock_get.side_effect = [error1, error2, mock_response]
        
        # Call the method with 3 max retries
        result = self.scraper.fetch_url('https://example.com', max_retries=3, backoff_factor=0.1)
        
        # Verify the result
        self.assertEqual(result, mock_response)
        self.assertEqual(mock_get.call_count, 3)
    
    @patch('web_scraper_module.GeneralScraper.fetch_url')
    def test_get_soup_success(self, mock_fetch_url):
        """Test successful creation of BeautifulSoup object."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.text = self.sample_html
        mock_fetch_url.return_value = mock_response
        
        # Call the method
        result = self.scraper.get_soup('https://example.com')
        
        # Verify the result
        self.assertIsInstance(result, BeautifulSoup)
        self.assertEqual(result.title.text, 'Test Page')
        
        # Verify that fetch_url was called correctly
        mock_fetch_url.assert_called_once_with('https://example.com', 3, 0.5)
    
    @patch('web_scraper_module.GeneralScraper.fetch_url')
    def test_get_soup_fetch_failure(self, mock_fetch_url):
        """Test handling of fetch_url returning None."""
        # Configure mock
        mock_fetch_url.return_value = None
        
        # Call the method
        result = self.scraper.get_soup('https://example.com')
        
        # Verify the result
        self.assertIsNone(result)
    
    @patch('web_scraper_module.GeneralScraper.fetch_url')
    def test_get_soup_parse_error(self, mock_fetch_url):
        """Test handling of BeautifulSoup parsing errors."""
        # Configure mock to return invalid HTML
        mock_response = MagicMock()
        mock_response.text = "Invalid HTML>>>>"
        mock_fetch_url.return_value = mock_response
        
        # Call the method
        result = self.scraper.get_soup('https://example.com')
        
        # Parsing should still succeed but warning about no body should be logged
        self.assertIsInstance(result, BeautifulSoup)
        self.assertIn('No <body> tag found in the HTML', self.log_capture.getvalue())
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_extract_links_success(self, mock_get_soup):
        """Test successful link extraction."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Call the method
        links = self.scraper.extract_links('https://example.com')
        
        # Verify the result
        self.assertEqual(len(links), 4)  # 4 links in our sample HTML
        self.assertIn('https://example.com/link1', links)
        self.assertIn('https://example.com/link2', links)
        self.assertIn('https://example.com/link4', links)
        
        # Verify relative link was converted to absolute
        self.assertIn('https://example.com/relative/link3', links)
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_extract_links_with_filter(self, mock_get_soup):
        """Test link extraction with filtering."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Call the method with filter
        links = self.scraper.extract_links('https://example.com', filter_pattern='link2')
        
        # Verify the result
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0], 'https://example.com/link2')
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_extract_links_with_link_text(self, mock_get_soup):
        """Test link extraction with link text."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Call the method with keep_link_text=True
        links = self.scraper.extract_links('https://example.com', keep_link_text=True)
        
        # Verify the result
        self.assertEqual(len(links), 4)
        self.assertIn(('https://example.com/link1', 'Link 1'), links)
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_extract_links_custom_selector(self, mock_get_soup):
        """Test link extraction with custom CSS selector."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Call the method with custom selector
        links = self.scraper.extract_links('https://example.com', css_selector='ul.links a')
        
        # Verify the result
        self.assertEqual(len(links), 3)
        self.assertIn('https://example.com/link2', links)
        self.assertIn('https://example.com/link4', links)
        self.assertIn('https://example.com/relative/link3', links)
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_extract_links_custom_attribute(self, mock_get_soup):
        """Test link extraction with custom attribute."""
        # Configure mock with HTML that has custom attributes
        html = """
        <div>
            <button data-url="https://example.com/button1">Button 1</button>
            <button data-url="https://example.com/button2">Button 2</button>
        </div>
        """
        mock_get_soup.return_value = BeautifulSoup(html, 'html.parser')
        
        # Call the method with custom attribute
        links = self.scraper.extract_links(
            'https://example.com',
            css_selector='button',
            attribute='data-url'
        )
        
        # Verify the result
        self.assertEqual(len(links), 2)
        self.assertIn('https://example.com/button1', links)
        self.assertIn('https://example.com/button2', links)
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_extract_links_no_soup(self, mock_get_soup):
        """Test link extraction when soup is None."""
        # Configure mock
        mock_get_soup.return_value = None
        
        # Call the method
        links = self.scraper.extract_links('https://example.com')
        
        # Verify the result
        self.assertEqual(links, [])
    
    def test_extract_elements_success(self):
        """Test successful element extraction."""
        # Call the method
        elements = self.scraper.extract_elements(self.sample_soup, 'p')
        
        # Verify the result
        self.assertEqual(len(elements), 3)
        # Note the space between 'with' and 'Link 1'
        self.assertEqual(elements[0]['text'], 'First paragraph with Link 1')
        self.assertEqual(elements[0]['element_type'], 'p')
    
    def test_extract_elements_with_attributes(self):
        """Test element extraction with attributes."""
        # Call the method with attributes
        elements = self.scraper.extract_elements(
            self.sample_soup,
            'div.product',
            extract_attrs=['id', 'data-price']
        )
        
        # Verify the result
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0]['id'], 'product1')
        self.assertEqual(elements[0]['data-price'], '19.99')
    
    def test_extract_elements_no_matches(self):
        """Test element extraction with no matching elements."""
        # Call the method with selector that doesn't match
        elements = self.scraper.extract_elements(self.sample_soup, 'div.non-existent')
        
        # Verify the result
        self.assertEqual(elements, [])
    
    def test_extract_elements_invalid_soup(self):
        """Test element extraction with invalid soup object."""
        # Call the method with invalid soup
        with self.assertRaises(TypeError):
            self.scraper.extract_elements("not a soup object", 'p')
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_extract_structured_data_success(self, mock_get_soup):
        """Test successful structured data extraction."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Define extraction config
        config = {
            'title': {
                'type': 'text',
                'selector': 'h1.main-title'
            },
            'paragraphs': {
                'type': 'elements',
                'selector': 'p',
                'attributes': []
            },
            'product_price': {
                'type': 'attribute',
                'selector': 'div.product',
                'attribute': 'data-price'
            },
            'product_image': {
                'type': 'attribute',
                'selector': 'img',
                'attribute': 'src'
            }
        }
        
        # Call the method
        result = self.scraper.extract_structured_data('https://example.com', config)
        
        # Verify the result
        self.assertEqual(result['title'], 'Main Title')
        self.assertEqual(len(result['paragraphs']), 3)
        self.assertEqual(result['product_price'], '19.99')
        self.assertEqual(result['product_image'], '/images/product.jpg')
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_extract_structured_data_regex(self, mock_get_soup):
        """Test structured data extraction with regex."""
        # Configure mock with HTML containing text to extract via regex
        html = """
        <div class="product-info">
            Product ID: ABC123
            <p>Price: $29.99</p>
        </div>
        """
        mock_get_soup.return_value = BeautifulSoup(html, 'html.parser')
        
        # Define extraction config with regex
        config = {
            'product_id': {
                'type': 'regex',
                'selector': 'div.product-info',
                'pattern': r'Product ID: (\w+)'
            },
            'price': {
                'type': 'regex',
                'selector': 'p',
                'pattern': r'\$(\d+\.\d{2})'
            }
        }
        
        # Call the method
        result = self.scraper.extract_structured_data('https://example.com', config)
        
        # Verify the result
        self.assertEqual(result['product_id'], 'ABC123')
        self.assertEqual(result['price'], '29.99')
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_extract_structured_data_custom_function(self, mock_get_soup):
        """Test structured data extraction with custom function."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Define custom extraction function
        def extract_link_count(soup):
            return len(soup.find_all('a'))
        
        # Define extraction config with custom function
        config = {
            'link_count': {
                'type': 'custom',
                'function': extract_link_count
            }
        }
        
        # Call the method
        result = self.scraper.extract_structured_data('https://example.com', config)
        
        # Verify the result
        self.assertEqual(result['link_count'], 4)  # 4 links in our sample HTML
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_extract_structured_data_no_soup(self, mock_get_soup):
        """Test structured data extraction when soup is None."""
        # Configure mock
        mock_get_soup.return_value = None
        
        # Call the method
        result = self.scraper.extract_structured_data('https://example.com', {})
        
        # Verify the result
        self.assertEqual(result, {'error': 'Failed to fetch URL', 'url': 'https://example.com'})


class TestCourtCaseScraper(unittest.TestCase):
    """Test cases for the CourtCaseScraper class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a test logger
        self.test_logger = logging.getLogger('test_court_scraper')
        self.test_logger.setLevel(logging.INFO)
        
        # Create a scraper instance with our test logger
        self.scraper = CourtCaseScraper(logger=self.test_logger)
        
        # Sample HTML content for testing
        self.sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Smith v. Jones - Supreme Court Case</title>
        </head>
        <body>
            <h2 class="heading">Supreme Court of the United States</h2>
            <strong class="heading">Smith v. Jones, 123 U.S. 456 (2020)</strong>
            
            <div class="content">
                <p>Argued January 5, 2020—Decided March 15, 2020</p>
                <p>This is the first paragraph of the case text.</p>
                <p>This is the second paragraph of the case text.</p>
                
                <h3>OPINION</h3>
                <div id="tab-opinion-1">
                    <p>Justice Smith delivered the opinion of the Court.</p>
                    <p>This is the first paragraph of the opinion text.</p>
                </div>
                
                <p><a name="F1">1. This is a footnote.</a></p>
            </div>
            
            <div class="search-case">
                <a href="https://example.com/cite/123us456" title="Citation">Official Citation</a>
                <a href="https://example.com/full/smith-v-jones" title="Full Text">Full Text</a>
            </div>
        </body>
        </html>
        """
        self.sample_soup = BeautifulSoup(self.sample_html, 'html.parser')
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_parse_case_page_success(self, mock_get_soup):
        """Test successful court case parsing."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Call the method
        result = self.scraper.parse_case_page('https://example.com/case')
        
        # Verify the result
        self.assertIn('case_info', result)
        self.assertIn('header_text', result)
        self.assertIn('case_text', result)
        self.assertIn('opinions', result)
        self.assertIn('footnotes', result)
        
        # Check case info
        self.assertEqual(result['case_info']['court'], 'Supreme Court of the United States')
        self.assertEqual(result['case_info']['title'], 'Smith v. Jones, 123 U.S. 456 (2020)')
        self.assertEqual(result['case_info']['citation'], '123 U.S. 456 (2020)')
        self.assertEqual(result['case_info']['date'], 'March 15, 2020')
        
        # Check header text
        self.assertEqual(len(result['header_text']), 2)
        
        # Check case text
        self.assertEqual(len(result['case_text']), 2)
        self.assertEqual(result['case_text'][0]['text'], 'This is the first paragraph of the case text.')
        
        # Check opinions
        self.assertEqual(len(result['opinions']), 2)
        self.assertEqual(result['opinions'][0]['text'], 'Justice Smith delivered the opinion of the Court.')
        
        # Check footnotes
        self.assertEqual(len(result['footnotes']), 1)
        self.assertEqual(result['footnotes'][0]['text'], '1. This is a footnote.')
        
        # Check external links
        self.assertEqual(len(result['case_info']['external_links']), 2)
        self.assertEqual(result['case_info']['external_links'][0]['text'], 'Official Citation')
    
    @patch('web_scraper_module.GeneralScraper.get_soup')
    def test_parse_case_page_no_soup(self, mock_get_soup):
        """Test court case parsing when soup is None."""
        # Configure mock
        mock_get_soup.return_value = None
        
        # Call the method
        result = self.scraper.parse_case_page('https://example.com/case')
        
        # Verify the result
        self.assertEqual(result, {'error': 'Failed to fetch URL', 'url': 'https://example.com/case'})
    
    def test_extract_case_info(self):
        """Test the _extract_case_info method."""
        # Call the method
        case_info = self.scraper._extract_case_info(self.sample_soup)
        
        # Verify the result - fixed to expect March 15, 2020
        self.assertEqual(case_info['court'], 'Supreme Court of the United States')
        self.assertEqual(case_info['title'], 'Smith v. Jones, 123 U.S. 456 (2020)')
        self.assertEqual(case_info['citation'], '123 U.S. 456 (2020)')
        self.assertEqual(case_info['date'], 'March 15, 2020')
        self.assertEqual(len(case_info['external_links']), 2)
    
    def test_filter_case_text(self):
        """Test the _filter_case_text method."""
        # Create some test data
        case_text = [
            {'text': 'This is a normal paragraph.', 'element_type': 'p', 'location': 'p-0'},
            {'text': 'This is a duplicate paragraph.', 'element_type': 'p', 'location': 'p-1'},
            {'text': 'This is a duplicate paragraph.', 'element_type': 'p', 'location': 'p-2'},
            {'text': 'Short', 'element_type': 'p', 'location': 'p-3'},
            {'text': 'Click next page to continue.', 'element_type': 'p', 'location': 'p-4'}
        ]
        
        # Call the method
        filtered = self.scraper._filter_case_text(case_text)
        
        # Verify the result - now expecting 2 items (the normal paragraph and one duplicate)
        self.assertEqual(len(filtered), 2)
        texts = [item['text'] for item in filtered]
        self.assertIn('This is a normal paragraph.', texts)
        self.assertIn('This is a duplicate paragraph.', texts)
    
    def test_filter_opinions(self):
        """Test the _filter_opinions method."""
        # Create some test data
        opinions = [
            {'text': 'Justice Smith delivered the opinion.', 'element_type': 'p', 'location': 'p-0'},
            {'text': 'Justice Smith delivered the opinion.', 'element_type': 'p', 'location': 'p-1'},
            {'text': 'Short', 'element_type': 'p', 'location': 'p-2'}
        ]
        
        # Call the method
        filtered = self.scraper._filter_opinions(opinions)
        
        # Verify the result
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['text'], 'Justice Smith delivered the opinion.')


if __name__ == '__main__':
    unittest.main()



class TestGeneralScraper(unittest.TestCase):
    """Test cases for the GeneralScraper class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a test logger that writes to a string buffer
        self.log_capture = io.StringIO()
        handler = logging.StreamHandler(self.log_capture)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        
        self.test_logger = logging.getLogger('test_logger')
        self.test_logger.setLevel(logging.INFO)
        for h in self.test_logger.handlers:
            self.test_logger.removeHandler(h)
        self.test_logger.addHandler(handler)
        
        # Create a scraper instance with our test logger
        self.scraper = GeneralScraper(logger=self.test_logger)
        
        # Sample HTML content for testing
        self.sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
        </head>
        <body>
            <h1 class="main-title">Main Title</h1>
            <div class="content">
                <p>First paragraph with <a href="https://example.com/link1">Link 1</a></p>
                <p>Second paragraph</p>
                <h2 id="section1">Section 1</h2>
                <p>Section 1 content</p>
                <ul class="links">
                    <li><a href="https://example.com/link2" class="external">Link 2</a></li>
                    <li><a href="/relative/link3">Link 3</a></li>
                    <li><a href="https://example.com/link4">Link 4</a></li>
                </ul>
                <div class="product" id="product1" data-price="19.99">
                    <h3>Product Title</h3>
                    <span class="price">$19.99</span>
                    <img src="/images/product.jpg" alt="Product Image" />
                </div>
            </div>
        </body>
        </html>
        """
        self.sample_soup = BeautifulSoup(self.sample_html, 'html.parser')
    
    def tearDown(self):
        """Clean up after each test method."""
        handlers = self.test_logger.handlers[:]
        for handler in handlers:
            self.test_logger.removeHandler(handler)
            handler.close()
    
    def test_init_default_logger(self):
        """Test that the default logger is created correctly."""
        scraper = GeneralScraper()
        self.assertIsNotNone(scraper.logger)
        self.assertEqual(scraper.logger.name, 'GeneralScraper')
    
    def test_init_custom_logger(self):
        """Test that a custom logger can be provided."""
        self.assertEqual(self.scraper.logger, self.test_logger)
    
    def test_init_custom_headers(self):
        """Test that custom headers can be provided."""
        custom_headers = {'User-Agent': 'Custom/1.0', 'X-Test': 'Test'}
        scraper = GeneralScraper(headers=custom_headers)
        self.assertEqual(scraper.headers, custom_headers)
    
    def test_init_custom_user_agent(self):
        """Test that a custom user agent can be provided."""
        custom_user_agent = 'CustomBot/1.0'
        scraper = GeneralScraper(user_agent=custom_user_agent)
        self.assertEqual(scraper.headers['User-Agent'], custom_user_agent)
    
    @patch('requests.get')
    def test_fetch_url_success(self, mock_get):
        """Test successful URL fetching."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.text = self.sample_html
        mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        mock_get.return_value = mock_response
        
        # Call the method
        result = self.scraper.fetch_url('https://example.com')
        
        # Verify the result
        self.assertEqual(result, mock_response)
        mock_get.assert_called_once_with(
            'https://example.com',
            headers=self.scraper.headers,
            timeout=self.scraper.timeout
        )
    
    @patch('requests.get')
    def test_fetch_url_invalid_url(self, mock_get):
        """Test that an invalid URL raises ValueError."""
        with self.assertRaises(ValueError):
            self.scraper.fetch_url('invalid-url')
        
        mock_get.assert_not_called()
    
    @patch('requests.get')
    def test_fetch_url_empty_response(self, mock_get):
        """Test handling of empty response."""
        # Configure mock for empty response
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        mock_get.return_value = mock_response
        
        # First call succeeds but raises ValueError for empty content
        mock_get.side_effect = [mock_response]
        
        # Call the method
        with self.assertRaises(ValueError):
            self.scraper.fetch_url('https://example.com', max_retries=1)
        
        # Verify that the error was logged
        self.assertIn('Empty response received', self.log_capture.getvalue())
    
    @patch('requests.get')
    def test_fetch_url_timeout(self, mock_get):
        """Test handling of timeout errors with retries."""
        # Configure mock to raise Timeout twice then succeed
        mock_response = MagicMock()
        mock_response.text = self.sample_html
        mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        
        mock_get.side_effect = [
            requests.exceptions.Timeout("Connection timed out"),
            requests.exceptions.Timeout("Connection timed out"),
            mock_response
        ]
        
        # Call the method with 3 max retries
        result = self.scraper.fetch_url('https://example.com', max_retries=3, backoff_factor=0.1)
        
        # Verify the result
        self.assertEqual(result, mock_response)
        self.assertEqual(mock_get.call_count, 3)
        
        # Verify that timeouts were logged
        log_output = self.log_capture.getvalue()
        self.assertIn('Request timed out', log_output)
        self.assertIn('Waiting', log_output)
    
    @patch('requests.get')
    def test_fetch_url_max_retries_exceeded(self, mock_get):
        """Test that max retries exceeded returns None."""
        # Configure mock to always raise Timeout
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        # Call the method with 3 max retries
        result = self.scraper.fetch_url('https://example.com', max_retries=3, backoff_factor=0.1)
        
        # Verify the result
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, 3)
        
        # Verify that failure was logged
        self.assertIn('Failed to fetch URL after 3 attempts', self.log_capture.getvalue())
    
    @patch('requests.get')
    def test_fetch_url_http_client_error(self, mock_get):
        """Test that HTTP client errors (4xx) are not retried."""
        # Configure mock to raise HTTPError with a 404 status code
        response = MagicMock()
        response.status_code = 404
        error = requests.exceptions.HTTPError("404 Client Error", response=response)
        mock_get.side_effect = error
        
        # Call the method
        with self.assertRaises(requests.exceptions.HTTPError):
            self.scraper.fetch_url('https://example.com', max_retries=3)
        
        # Verify that it only tried once and didn't retry
        self.assertEqual(mock_get.call_count, 1)
        
        # Verify that error was logged
        self.assertIn('HTTP error 404', self.log_capture.getvalue())
    
    @patch('requests.get')
    def test_fetch_url_http_server_error(self, mock_get):
        """Test that HTTP server errors (5xx) are retried."""
        # Configure mock to raise HTTPError twice with 500, then succeed
        response1 = MagicMock()
        response1.status_code = 500
        error1 = requests.exceptions.HTTPError("500 Server Error", response=response1)
        
        response2 = MagicMock()
        response2.status_code = 500
        error2 = requests.exceptions.HTTPError("500 Server Error", response=response2)
        
        mock_response = MagicMock()
        mock_response.text = self.sample_html
        mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        
        mock_get.side_effect = [error1, error2, mock_response]
        
        # Call the method with 3 max retries
        result = self.scraper.fetch_url('https://example.com', max_retries=3, backoff_factor=0.1)
        
        # Verify the result
        self.assertEqual(result, mock_response)
        self.assertEqual(mock_get.call_count, 3)
    
    @patch('test_webscraping_html_extractor.GeneralScraper.fetch_url')
    def test_get_soup_success(self, mock_fetch_url):
        """Test successful creation of BeautifulSoup object."""
        # Configure mock
        mock_response = MagicMock()
        mock_response.text = self.sample_html
        mock_fetch_url.return_value = mock_response
        
        # Call the method
        result = self.scraper.get_soup('https://example.com')
        
        # Verify the result
        self.assertIsInstance(result, BeautifulSoup)
        self.assertEqual(result.title.text, 'Test Page')
        
        # Verify that fetch_url was called correctly
        mock_fetch_url.assert_called_once_with('https://example.com', 3, 0.5)
    
    @patch('test_webscraping_html_extractor.GeneralScraper.fetch_url')
    def test_get_soup_fetch_failure(self, mock_fetch_url):
        """Test handling of fetch_url returning None."""
        # Configure mock
        mock_fetch_url.return_value = None
        
        # Call the method
        result = self.scraper.get_soup('https://example.com')
        
        # Verify the result
        self.assertIsNone(result)
    
    @patch('test_webscraping_html_extractor.GeneralScraper.fetch_url')
    def test_get_soup_parse_error(self, mock_fetch_url):
        """Test handling of BeautifulSoup parsing errors."""
        # Configure mock to return invalid HTML
        mock_response = MagicMock()
        mock_response.text = "Invalid HTML>>>>"
        mock_fetch_url.return_value = mock_response
        
        # Call the method
        result = self.scraper.get_soup('https://example.com')
        
        # Parsing should still succeed but warning about no body should be logged
        self.assertIsInstance(result, BeautifulSoup)
        self.assertIn('No <body> tag found in the HTML', self.log_capture.getvalue())
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_extract_links_success(self, mock_get_soup):
        """Test successful link extraction."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Call the method
        links = self.scraper.extract_links('https://example.com')
        
        # Verify the result
        self.assertEqual(len(links), 4)  # 4 links in our sample HTML
        self.assertIn('https://example.com/link1', links)
        self.assertIn('https://example.com/link2', links)
        self.assertIn('https://example.com/link4', links)
        
        # Verify relative link was converted to absolute
        self.assertIn('https://example.com/relative/link3', links)
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_extract_links_with_filter(self, mock_get_soup):
        """Test link extraction with filtering."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Call the method with filter
        links = self.scraper.extract_links('https://example.com', filter_pattern='link2')
        
        # Verify the result
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0], 'https://example.com/link2')
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_extract_links_with_link_text(self, mock_get_soup):
        """Test link extraction with link text."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Call the method with keep_link_text=True
        links = self.scraper.extract_links('https://example.com', keep_link_text=True)
        
        # Verify the result
        self.assertEqual(len(links), 4)
        self.assertIn(('https://example.com/link1', 'Link 1'), links)
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_extract_links_custom_selector(self, mock_get_soup):
        """Test link extraction with custom CSS selector."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Call the method with custom selector
        links = self.scraper.extract_links('https://example.com', css_selector='ul.links a')
        
        # Verify the result
        self.assertEqual(len(links), 3)
        self.assertIn('https://example.com/link2', links)
        self.assertIn('https://example.com/link4', links)
        self.assertIn('https://example.com/relative/link3', links)
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_extract_links_custom_attribute(self, mock_get_soup):
        """Test link extraction with custom attribute."""
        # Configure mock with HTML that has custom attributes
        html = """
        <div>
            <button data-url="https://example.com/button1">Button 1</button>
            <button data-url="https://example.com/button2">Button 2</button>
        </div>
        """
        mock_get_soup.return_value = BeautifulSoup(html, 'html.parser')
        
        # Call the method with custom attribute
        links = self.scraper.extract_links(
            'https://example.com',
            css_selector='button',
            attribute='data-url'
        )
        
        # Verify the result
        self.assertEqual(len(links), 2)
        self.assertIn('https://example.com/button1', links)
        self.assertIn('https://example.com/button2', links)
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_extract_links_no_soup(self, mock_get_soup):
        """Test link extraction when soup is None."""
        # Configure mock
        mock_get_soup.return_value = None
        
        # Call the method
        links = self.scraper.extract_links('https://example.com')
        
        # Verify the result
        self.assertEqual(links, [])
    
    def test_extract_elements_success(self):
        """Test successful element extraction."""
        # Call the method
        elements = self.scraper.extract_elements(self.sample_soup, 'p')
        
        # Verify the result
        self.assertEqual(len(elements), 3)
        self.assertEqual(elements[0]['text'], 'First paragraph with Link 1')
        self.assertEqual(elements[0]['element_type'], 'p')
    
    def test_extract_elements_with_attributes(self):
        """Test element extraction with attributes."""
        # Call the method with attributes
        elements = self.scraper.extract_elements(
            self.sample_soup,
            'div.product',
            extract_attrs=['id', 'data-price']
        )
        
        # Verify the result
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0]['id'], 'product1')
        self.assertEqual(elements[0]['data-price'], '19.99')
    
    def test_extract_elements_no_matches(self):
        """Test element extraction with no matching elements."""
        # Call the method with selector that doesn't match
        elements = self.scraper.extract_elements(self.sample_soup, 'div.non-existent')
        
        # Verify the result
        self.assertEqual(elements, [])
    
    def test_extract_elements_invalid_soup(self):
        """Test element extraction with invalid soup object."""
        # Call the method with invalid soup
        with self.assertRaises(TypeError):
            self.scraper.extract_elements("not a soup object", 'p')
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_extract_structured_data_success(self, mock_get_soup):
        """Test successful structured data extraction."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Define extraction config
        config = {
            'title': {
                'type': 'text',
                'selector': 'h1.main-title'
            },
            'paragraphs': {
                'type': 'elements',
                'selector': 'p',
                'attributes': []
            },
            'product_price': {
                'type': 'attribute',
                'selector': 'div.product',
                'attribute': 'data-price'
            },
            'product_image': {
                'type': 'attribute',
                'selector': 'img',
                'attribute': 'src'
            }
        }
        
        # Call the method
        result = self.scraper.extract_structured_data('https://example.com', config)
        
        # Verify the result
        self.assertEqual(result['title'], 'Main Title')
        self.assertEqual(len(result['paragraphs']), 3)
        self.assertEqual(result['product_price'], '19.99')
        self.assertEqual(result['product_image'], '/images/product.jpg')
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_extract_structured_data_regex(self, mock_get_soup):
        """Test structured data extraction with regex."""
        # Configure mock with HTML containing text to extract via regex
        html = """
        <div class="product-info">
            Product ID: ABC123
            <p>Price: $29.99</p>
        </div>
        """
        mock_get_soup.return_value = BeautifulSoup(html, 'html.parser')
        
        # Define extraction config with regex
        config = {
            'product_id': {
                'type': 'regex',
                'selector': 'div.product-info',
                'pattern': r'Product ID: (\w+)'
            },
            'price': {
                'type': 'regex',
                'selector': 'p',
                'pattern': r'\$(\d+\.\d{2})'
            }
        }
        
        # Call the method
        result = self.scraper.extract_structured_data('https://example.com', config)
        
        # Verify the result
        self.assertEqual(result['product_id'], 'ABC123')
        self.assertEqual(result['price'], '29.99')
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_extract_structured_data_custom_function(self, mock_get_soup):
        """Test structured data extraction with custom function."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Define custom extraction function
        def extract_link_count(soup):
            return len(soup.find_all('a'))
        
        # Define extraction config with custom function
        config = {
            'link_count': {
                'type': 'custom',
                'function': extract_link_count
            }
        }
        
        # Call the method
        result = self.scraper.extract_structured_data('https://example.com', config)
        
        # Verify the result
        self.assertEqual(result['link_count'], 4)  # 4 links in our sample HTML
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_extract_structured_data_no_soup(self, mock_get_soup):
        """Test structured data extraction when soup is None."""
        # Configure mock
        mock_get_soup.return_value = None
        
        # Call the method
        result = self.scraper.extract_structured_data('https://example.com', {})
        
        # Verify the result
        self.assertEqual(result, {'error': 'Failed to fetch URL', 'url': 'https://example.com'})


class TestCourtCaseScraper(unittest.TestCase):
    """Test cases for the CourtCaseScraper class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a test logger
        self.test_logger = logging.getLogger('test_court_scraper')
        self.test_logger.setLevel(logging.INFO)
        
        # Create a scraper instance with our test logger
        self.scraper = CourtCaseScraper(logger=self.test_logger)
        
        # Sample HTML content for testing
        self.sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Smith v. Jones - Supreme Court Case</title>
        </head>
        <body>
            <h2 class="heading">Supreme Court of the United States</h2>
            <strong class="heading">Smith v. Jones, 123 U.S. 456 (2020)</strong>
            
            <div class="content">
                <p>Argued January 5, 2020—Decided March 15, 2020</p>
                <p>This is the first paragraph of the case text.</p>
                <p>This is the second paragraph of the case text.</p>
                
                <h3>OPINION</h3>
                <div id="tab-opinion-1">
                    <p>Justice Smith delivered the opinion of the Court.</p>
                    <p>This is the first paragraph of the opinion text.</p>
                </div>
                
                <p><a name="F1">1. This is a footnote.</a></p>
            </div>
            
            <div class="search-case">
                <a href="https://example.com/cite/123us456" title="Citation">Official Citation</a>
                <a href="https://example.com/full/smith-v-jones" title="Full Text">Full Text</a>
            </div>
        </body>
        </html>
        """
        self.sample_soup = BeautifulSoup(self.sample_html, 'html.parser')
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_parse_case_page_success(self, mock_get_soup):
        """Test successful court case parsing."""
        # Configure mock
        mock_get_soup.return_value = self.sample_soup
        
        # Call the method
        result = self.scraper.parse_case_page('https://example.com/case')
        
        # Verify the result
        self.assertIn('case_info', result)
        self.assertIn('header_text', result)
        self.assertIn('case_text', result)
        self.assertIn('opinions', result)
        self.assertIn('footnotes', result)
        
        # Check case info
        self.assertEqual(result['case_info']['court'], 'Supreme Court of the United States')
        self.assertEqual(result['case_info']['title'], 'Smith v. Jones, 123 U.S. 456 (2020)')
        self.assertEqual(result['case_info']['citation'], '123 U.S. 456 (2020)')
        self.assertEqual(result['case_info']['date'], 'March 15, 2020')
        
        # Check header text
        self.assertEqual(len(result['header_text']), 2)
        
        # Check case text
        self.assertEqual(len(result['case_text']), 2)
        self.assertEqual(result['case_text'][0]['text'], 'This is the first paragraph of the case text.')
        
        # Check opinions
        self.assertEqual(len(result['opinions']), 2)
        self.assertEqual(result['opinions'][0]['text'], 'Justice Smith delivered the opinion of the Court.')
        
        # Check footnotes
        self.assertEqual(len(result['footnotes']), 1)
        self.assertEqual(result['footnotes'][0]['text'], '1. This is a footnote.')
        
        # Check external links
        self.assertEqual(len(result['case_info']['external_links']), 2)
        self.assertEqual(result['case_info']['external_links'][0]['text'], 'Official Citation')
    
    @patch('test_webscraping_html_extractor.GeneralScraper.get_soup')
    def test_parse_case_page_no_soup(self, mock_get_soup):
        """Test court case parsing when soup is None."""
        # Configure mock
        mock_get_soup.return_value = None
        
        # Call the method
        result = self.scraper.parse_case_page('https://example.com/case')
        
        # Verify the result
        self.assertEqual(result, {'error': 'Failed to fetch URL', 'url': 'https://example.com/case'})
    
    def test_extract_case_info(self):
        """Test the _extract_case_info method."""
        # Call the method
        case_info = self.scraper._extract_case_info(self.sample_soup)
        
        # Verify the result
        self.assertEqual(case_info['court'], 'Supreme Court of the United States')
        self.assertEqual(case_info['title'], 'Smith v. Jones, 123 U.S. 456 (2020)')
        self.assertEqual(case_info['citation'], '123 U.S. 456 (2020)')
        self.assertEqual(case_info['date'], 'March 15, 2020')
        self.assertEqual(len(case_info['external_links']), 2)
    
    def test_filter_case_text(self):
        """Test the _filter_case_text method."""
        # Create some test data
        case_text = [
            {'text': 'This is a normal paragraph.', 'element_type': 'p', 'location': 'p-0'},
            {'text': 'This is a duplicate paragraph.', 'element_type': 'p', 'location': 'p-1'},
            {'text': 'This is a duplicate paragraph.', 'element_type': 'p', 'location': 'p-2'},
            {'text': 'Short', 'element_type': 'p', 'location': 'p-3'},
            {'text': 'Click next page to continue.', 'element_type': 'p', 'location': 'p-4'}
        ]
        
        # Call the method
        filtered = self.scraper._filter_case_text(case_text)
        
        # Verify the result
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['text'], 'This is a normal paragraph.')
    
    def test_filter_opinions(self):
        """Test the _filter_opinions method."""
        # Create some test data
        opinions = [
            {'text': 'Justice Smith delivered the opinion.', 'element_type': 'p', 'location': 'p-0'},
            {'text': 'Justice Smith delivered the opinion.', 'element_type': 'p', 'location': 'p-1'},
            {'text': 'Short', 'element_type': 'p', 'location': 'p-2'}
        ]
        
        # Call the method
        filtered = self.scraper._filter_opinions(opinions)
        
        # Verify the result
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['text'], 'Justice Smith delivered the opinion.')

