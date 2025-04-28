import pandas as pd
import logging
from typing import Optional, Union, List, Dict, Any

class WebPageTableExtractor:
    """
    A class for extracting tables from web pages using pandas.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the extractor with optional custom logger.
        
        Args:
            logger: Optional custom logger instance
        """
        # Set up logging
        self.logger = logger or self._setup_default_logger()
    
    @staticmethod
    def _setup_default_logger():
        """Create and configure a default logger."""
        logger = logging.getLogger('WebPageTableExtractor')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def _fetch_tables(self, url: str) -> Optional[List[pd.DataFrame]]:
        """
        Internal method to fetch all tables from a URL.
        
        Args:
            url: The URL to fetch tables from
            
        Returns:
            List of DataFrames or None if failed
        """
        try:
            tables = pd.read_html(url)
            return tables
        except Exception as e:
            self.logger.error(f"Error fetching tables from {url}: {e}")
            self.logger.debug("Exception details:", exc_info=True)
            return None
    
    def extract_table(self, url: str, table_index: int = 0) -> Optional[pd.DataFrame]:
        """
        Extract a specific table from a web page.
        
        Args:
            url: Full URL of the web page
            table_index: Index of the table to extract (0 for the first table)
            
        Returns:
            pandas.DataFrame or None: The extracted table or None if extraction failed
        """
        tables = self._fetch_tables(url)
        
        if tables is None:
            return None
            
        if not tables:
            self.logger.warning(f"No tables found at {url}")
            return None
            
        if table_index >= len(tables):
            self.logger.warning(f"Table index {table_index} is out of range. There are only {len(tables)} tables.")
            return None
        
        # Get and process the specified table
        table = tables[table_index]
        return self._process_table(table)
    
    def extract_all_tables(self, url: str) -> List[pd.DataFrame]:
        """
        Extract all tables from a web page.
        
        Args:
            url: Full URL of the web page
            
        Returns:
            List of pandas.DataFrame: The extracted tables (empty list if none found)
        """
        tables = self._fetch_tables(url)
        
        if tables is None or not tables:
            return []
        
        # Process each table
        return [self._process_table(table) for table in tables]
    
    def _process_table(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process a DataFrame table by flattening multi-level columns and other cleaning.
        
        Args:
            df: The pandas DataFrame to process
            
        Returns:
            pandas.DataFrame: The processed DataFrame
        """
        # Handle multi-level columns
        df.columns = self._flatten_columns(df.columns)
        
        # Additional processing can be added here
        
        return df
    
    @staticmethod
    def _flatten_columns(columns: Union[pd.Index, pd.MultiIndex]) -> List[str]:
        """
        Flatten multi-level column names into single level.
        
        Args:
            columns: Column index, potentially multi-level
            
        Returns:
            List of flattened column names
        """
        if isinstance(columns, pd.MultiIndex):
            # Join the levels with underscore and remove duplicates
            flat_columns = []
            for col in columns:
                # Filter out empty strings and duplicates within the same column
                filtered_parts = []
                seen = set()
                for part in col:
                    if part and part not in seen:
                        filtered_parts.append(str(part))
                        seen.add(part)
                
                # Join with underscore
                new_col = '_'.join(filtered_parts)
                flat_columns.append(new_col)
            
            return flat_columns
        
        return list(columns)
    
    def get_table_info(self, url: str) -> Dict[str, Any]:
        """
        Get information about tables on a web page without downloading them.
        
        Args:
            url: Full URL of the web page
            
        Returns:
            Dictionary with information about available tables
        """
        try:
            tables = pd.read_html(url)
            
            return {
                'num_tables': len(tables),
                'table_shapes': [table.shape for table in tables],
                'table_columns': [list(self._flatten_columns(table.columns)) for table in tables]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting table info from {url}: {e}")
            return {'error': str(e), 'num_tables': 0}


# Example usage:
if __name__ == "__main__":
    # Create an extractor instance
    extractor = WebPageTableExtractor()
    
    # Extract a specific table
    url = "https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal)"
    table = extractor.extract_table(url, table_index=0)
    
    if table is not None:
        print(f"Table shape: {table.shape}")
        print(table.head())
    
    # Get info about all tables on the page
    info = extractor.get_table_info(url)
    print(f"Found {info['num_tables']} tables on the page")