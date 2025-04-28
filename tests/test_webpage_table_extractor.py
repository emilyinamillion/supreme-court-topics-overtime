import unittest
from unittest.mock import patch
import pandas as pd
import logging
import io

# Import the class we want to test
from webpage_table_extractor import WebPageTableExtractor

class TestRefactoredWebPageTableExtractor(unittest.TestCase):
    """Test cases for the refactored WebPageTableExtractor class"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        # Create a test logger that writes to a string buffer
        self.log_capture = io.StringIO()
        handler = logging.StreamHandler(self.log_capture)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        
        self.test_logger = logging.getLogger('test_logger')
        self.test_logger.setLevel(logging.INFO)
        self.test_logger.addHandler(handler)
        
        # Create an instance of WebPageTableExtractor with our test logger
        self.extractor = WebPageTableExtractor(logger=self.test_logger)
        
        # Sample dataframes for testing
        self.sample_df1 = pd.DataFrame({
            'A': [1, 2, 3],
            'B': ['a', 'b', 'c']
        })
        
        self.sample_df2 = pd.DataFrame({
            'C': [4, 5, 6],
            'D': ['d', 'e', 'f']
        })
        
    def tearDown(self):
        """Clean up after each test method"""
        handlers = self.test_logger.handlers[:]
        for handler in handlers:
            self.test_logger.removeHandler(handler)
            handler.close()
    
    @patch.object(WebPageTableExtractor, '_fetch_tables')
    def test_fetch_tables_called_by_extract_table(self, mock_fetch_tables):
        """Test that _fetch_tables is called by extract_table"""
        # Mock _fetch_tables to return a list with our sample dataframe
        mock_fetch_tables.return_value = [self.sample_df1, self.sample_df2]
        
        # Call extract_table
        result = self.extractor.extract_table('http://example.com', table_index=0)
        
        # Verify that _fetch_tables was called once with the URL
        mock_fetch_tables.assert_called_once_with('http://example.com')
        
        # Check that the result is our first sample dataframe
        pd.testing.assert_frame_equal(result, self.sample_df1)
    
    @patch.object(WebPageTableExtractor, '_fetch_tables')
    def test_fetch_tables_called_by_extract_all_tables(self, mock_fetch_tables):
        """Test that _fetch_tables is called by extract_all_tables"""
        # Mock _fetch_tables to return a list with our sample dataframes
        mock_fetch_tables.return_value = [self.sample_df1, self.sample_df2]
        
        # Call extract_all_tables
        results = self.extractor.extract_all_tables('http://example.com')
        
        # Verify that _fetch_tables was called once with the URL
        mock_fetch_tables.assert_called_once_with('http://example.com')
        
        # Check that the results contain both dataframes
        self.assertEqual(len(results), 2)
        pd.testing.assert_frame_equal(results[0], self.sample_df1)
        pd.testing.assert_frame_equal(results[1], self.sample_df2)
    
    @patch('pandas.read_html')
    def test_fetch_tables_success(self, mock_read_html):
        """Test _fetch_tables success case"""
        # Mock pandas.read_html to return a list with our sample dataframes
        mock_read_html.return_value = [self.sample_df1, self.sample_df2]
        
        # Call _fetch_tables directly
        results = self.extractor._fetch_tables('http://example.com')
        
        # Verify that read_html was called once with the URL
        mock_read_html.assert_called_once_with('http://example.com')
        
        # Check that the results contain both dataframes
        self.assertEqual(len(results), 2)
        pd.testing.assert_frame_equal(results[0], self.sample_df1)
        pd.testing.assert_frame_equal(results[1], self.sample_df2)
    
    @patch('pandas.read_html')
    def test_fetch_tables_exception(self, mock_read_html):
        """Test _fetch_tables when an exception occurs"""
        # Mock pandas.read_html to raise an exception
        mock_read_html.side_effect = Exception('Test error')
        
        # Call _fetch_tables directly
        result = self.extractor._fetch_tables('http://example.com')
        
        # Check that the result is None
        self.assertIsNone(result)
        
        # Check that an error was logged
        self.assertIn('ERROR: Error fetching tables from http://example.com: Test error', 
                     self.log_capture.getvalue())
    
    @patch.object(WebPageTableExtractor, '_fetch_tables')
    def test_extract_table_no_tables_found(self, mock_fetch_tables):
        """Test extract_table when _fetch_tables returns None"""
        # Mock _fetch_tables to return None (error case)
        mock_fetch_tables.return_value = None
        
        # Call extract_table
        result = self.extractor.extract_table('http://example.com')
        
        # Check that the result is None
        self.assertIsNone(result)
    
    @patch.object(WebPageTableExtractor, '_fetch_tables')
    def test_extract_table_empty_tables_list(self, mock_fetch_tables):
        """Test extract_table when _fetch_tables returns an empty list"""
        # Mock _fetch_tables to return an empty list
        mock_fetch_tables.return_value = []
        
        # Call extract_table
        result = self.extractor.extract_table('http://example.com')
        
        # Check that the result is None
        self.assertIsNone(result)
        
        # Check that a warning was logged
        self.assertIn('WARNING: No tables found at http://example.com', 
                     self.log_capture.getvalue())
    
    @patch.object(WebPageTableExtractor, '_fetch_tables')
    def test_extract_table_index_out_of_range(self, mock_fetch_tables):
        """Test extract_table with an index that's out of range"""
        # Mock _fetch_tables to return a list with one dataframe
        mock_fetch_tables.return_value = [self.sample_df1]
        
        # Call extract_table with an invalid index
        result = self.extractor.extract_table('http://example.com', table_index=1)
        
        # Check that the result is None
        self.assertIsNone(result)
        
        # Check that a warning was logged
        self.assertIn('WARNING: Table index 1 is out of range', 
                     self.log_capture.getvalue())
    
    @patch.object(WebPageTableExtractor, '_fetch_tables')
    def test_extract_all_tables_none_result(self, mock_fetch_tables):
        """Test extract_all_tables when _fetch_tables returns None"""
        # Mock _fetch_tables to return None (error case)
        mock_fetch_tables.return_value = None
        
        # Call extract_all_tables
        results = self.extractor.extract_all_tables('http://example.com')
        
        # Check that we got an empty list
        self.assertEqual(results, [])
    
    @patch.object(WebPageTableExtractor, '_fetch_tables')
    def test_extract_all_tables_empty_list(self, mock_fetch_tables):
        """Test extract_all_tables when _fetch_tables returns an empty list"""
        # Mock _fetch_tables to return an empty list
        mock_fetch_tables.return_value = []
        
        # Call extract_all_tables
        results = self.extractor.extract_all_tables('http://example.com')
        
        # Check that we got an empty list
        self.assertEqual(results, [])
    
    @patch.object(WebPageTableExtractor, '_process_table')
    @patch.object(WebPageTableExtractor, '_fetch_tables')
    def test_process_table_called_for_each_table(self, mock_fetch_tables, mock_process_table):
        """Test that _process_table is called for each table in extract_all_tables"""
        # Mock _fetch_tables to return a list with our sample dataframes
        mock_fetch_tables.return_value = [self.sample_df1, self.sample_df2]
        
        # Set up mock_process_table to return a simple value, not the input dataframe
        mock_process_table.side_effect = lambda df: "processed"
        
        # Call extract_all_tables
        self.extractor.extract_all_tables('http://example.com')
        
        # Check that _process_table was called twice
        self.assertEqual(mock_process_table.call_count, 2)
        
        # Get the actual arguments passed to _process_table
        call_args_list = mock_process_table.call_args_list
        self.assertEqual(len(call_args_list), 2)
        
        # Instead of directly comparing DataFrames, check that they have the same shape and values
        call_df1 = call_args_list[0][0][0]  # First call, first positional arg
        call_df2 = call_args_list[1][0][0]  # Second call, first positional arg
        
        # Check shapes
        self.assertEqual(call_df1.shape, self.sample_df1.shape)
        self.assertEqual(call_df2.shape, self.sample_df2.shape)
        
        # Check data equality using pandas testing utilities
        pd.testing.assert_frame_equal(call_df1, self.sample_df1)
        pd.testing.assert_frame_equal(call_df2, self.sample_df2)


# if __name__ == '__main__':
#     unittest.main()