# data_ingestion/document_loaders.py

import requests
import os
from pypdf import PdfReader
import re
import logging
from typing import Optional, Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DocumentLoader:
    """
    A class for loading and extracting text from various document types,
    primarily focusing on PDFs for earnings reports and analyst reports.
    """
    def __init__(self, download_dir: str = 'downloaded_docs'):
        """
        Initializes the DocumentLoader.

        Args:
            download_dir (str): Directory to store downloaded documents.
        """
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        logging.info(f"DocumentLoader initialized. Download directory: {self.download_dir}")

    def download_file(self, url: str, filename: Optional[str] = None) -> Optional[str]:
        """
        Downloads a file from a given URL to the specified download directory.

        Args:
            url (str): The URL of the file to download.
            filename (str, optional): The name to save the file as. If None,
                                      it tries to infer from the URL or assigns a generic name.

        Returns:
            str: The full path to the downloaded file if successful, None otherwise.
        """
        if not filename:
            filename = url.split('/')[-1] # Try to get filename from URL
            if '?' in filename: # Remove query parameters if present
                filename = filename.split('?')[0]
            if not filename or '.' not in filename: # Fallback if no clear filename
                filename = "downloaded_file" + str(hash(url))[:8] # Simple unique name

        file_path = os.path.join(self.download_dir, filename)

        try:
            logging.info(f"Attempting to download {url} to {file_path}")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

            # Check if content-type suggests a PDF if not already in filename
            content_type = response.headers.get('Content-Type', '')
            if 'pdf' in content_type and not filename.lower().endswith('.pdf'):
                file_path += '.pdf'
                logging.info(f"Appending .pdf extension based on Content-Type. New path: {file_path}")

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info(f"Successfully downloaded: {file_path}")
            return file_path
        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading {url}: {e}")
            return None
        except IOError as e:
            logging.error(f"Error writing file to disk {file_path}: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        """
        Performs basic cleaning on extracted text.
        - Removes excessive whitespace/newlines.
        - Removes common PDF artifacts (e.g., page numbers, headers/footers if simple).
        """
        # Remove common page number patterns (e.g., " - 12 - ")
        text = re.sub(r'\s*-\s*\d+\s*-\s*', '\n', text)
        # Remove multiple consecutive newlines, leaving at most two for paragraphs
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        # Remove multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        # Strip leading/trailing whitespace from each line
        text = '\n'.join([line.strip() for line in text.split('\n')])
        # Remove form feed characters if present (often from PDF conversions)
        text = text.replace('\x0c', '')
        return text.strip()

    def load_pdf_from_path(self, pdf_path: str) -> Optional[Dict[str, str]]:
        """
        Extracts text from a local PDF file.

        Args:
            pdf_path (str): The path to the PDF file.

        Returns:
            dict: A dictionary with 'file_path' and 'content' if successful, None otherwise.
        """
        if not os.path.exists(pdf_path):
            logging.error(f"PDF file not found at: {pdf_path}")
            return None
        if not pdf_path.lower().endswith('.pdf'):
            logging.warning(f"File {pdf_path} does not have a .pdf extension. Attempting to load anyway.")

        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            text_content = []

            logging.info(f"Extracting text from {total_pages} pages of {pdf_path}...")
            for page_num in range(total_pages):
                page = reader.pages[page_num]
                text = page.extract_text()
                if text:
                    text_content.append(text)
                else:
                    logging.warning(f"No text extracted from page {page_num + 1} of {pdf_path}")

            full_text = "\n".join(text_content)
            cleaned_text = self._clean_text(full_text)

            if not cleaned_text.strip():
                logging.warning(f"Extracted content from {pdf_path} is empty or only whitespace after cleaning.")
                return None

            logging.info(f"Successfully extracted text from {pdf_path}. Content length: {len(cleaned_text)} characters.")
            return {
                'file_path': pdf_path,
                'content': cleaned_text
            }
        except Exception as e:
            logging.error(f"Error loading PDF from {pdf_path}: {e}")
            return None

    def load_pdf_from_url(self, url: str, filename: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Downloads a PDF from a URL and then extracts its text content.

        Args:
            url (str): The URL of the PDF.
            filename (str, optional): The name to save the PDF as.

        Returns:
            dict: A dictionary with 'file_path' and 'content' if successful, None otherwise.
        """
        downloaded_path = self.download_file(url, filename)
        if downloaded_path:
            return self.load_pdf_from_path(downloaded_path)
        return None

# --- Example Usage ---
if __name__ == "__main__":
    loader = DocumentLoader()

    # --- Test 1: Load a local PDF (you'll need to place a dummy.pdf in downloaded_docs or elsewhere) ---
    print("\n--- Testing local PDF loading ---")
    local_pdf_path = os.path.join(loader.download_dir, "sample_report.pdf")
    # For testing, create a simple PDF file named 'sample_report.pdf' in the 'downloaded_docs' folder.
    # You can quickly create one from any document using a 'Print to PDF' option.
    # Alternatively, you can use a public sample PDF for initial testing if you don't have one handy.

    if os.path.exists(local_pdf_path):
        print(f"Attempting to load local PDF: {local_pdf_path}")
        local_content = loader.load_pdf_from_path(local_pdf_path)
        if local_content:
            print(f"Local PDF Content (first 500 chars):\n{local_content['content'][:500]}...")
        else:
            print(f"Failed to load local PDF: {local_pdf_path}")
    else:
        print(f"Skipping local PDF test: '{local_pdf_path}' not found. Please create one for testing.")
        print("You can use a public sample PDF for the next test.")

    # --- Test 2: Download and load a PDF from a URL ---
    print("\n--- Testing URL PDF loading ---")
    # Using a publicly available sample PDF for demonstration.
    # In a real scenario, this would be a link to an earnings report PDF.
    sample_pdf_url = "https://www.africau.edu/images/default/sample.pdf" # A generic sample PDF
    # For actual finance reports, find URLs like:
    # "https://ir.about.att.com/static-files/89c4458f-2875-47e0-9118-a664e12e131d" (AT&T 2023 Q4)
    # Be aware: these links might change or require specific headers.
    
    # Try a more relevant example if you find a stable one:
    # Example: A direct link to an SEC filing (e.g., 10-K, 10-Q) from a reputable source like SEC EDGAR.
    # For instance, search "Apple 10-K PDF" to find direct links to SEC filings.
    # e.g., "https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/aapl-20230930.htm"
    # Note: SEC filings are often HTML files with embedded PDFs or just HTML. The above link is HTML.
    # You need a direct PDF link.
    # Let's stick with the generic sample for now, as direct finance PDF links are highly dynamic.

    print(f"Attempting to download and load PDF from URL: {sample_pdf_url}")
    url_content = loader.load_pdf_from_url(sample_pdf_url, filename="downloaded_sample.pdf")
    if url_content:
        print(f"URL PDF Content (first 500 chars):\n{url_content['content'][:500]}...")
        # Optional: Clean up the downloaded file after testing
        # os.remove(url_content['file_path'])
        # print(f"Cleaned up {url_content['file_path']}")
    else:
        print(f"Failed to download or load PDF from URL: {sample_pdf_url}")