# getSiteLinks

**getSiteLinks** is a simple web crawler built using Scrapy. It starts from a specified URL (or a TOML configuration file) and extracts key metrics for each page visited. The metrics include:

- **url:** The page URL.
- **title:** The page title.
- **linkCount:** Number of unique `<a>` tags with an `href` attribute.
- **controlCount:** Number of elements with a non-empty ARIA role or native HTML controls.
- **byteCount:** The byte size of the HTML content (excluding external resources).
- **updated:** An estimated last-updated date (YYYY-MM-DD) derived from HTTP headers or meta tags.

The results are saved to a CSV file whose name is derived from the start page title. Optionally, a log file is also generated. Both the CSV and log files are written using UTF-8 with a Byte Order Mark (BOM) for compatibility.

## Features

- **Crawl Control:** Set maximum URLs and crawl depth.
- **Directory Filtering:** Optionally restrict URLs to a specific directory.
- **User Agent Randomization:** A random User-Agent header is assigned to each request from a pool of common agents (with an option to add a custom one) to minimize blocking.
- **Request Delay Randomization:** A randomized delay between requests is configured to mimic natural browsing behavior.
- **robots.txt Option:** Option to obey the robots.txt file (disabled by default).
- **Logging:** Optionally create a log file (with the same base name as the CSV) that captures detailed execution logs. When logging is not enabled, all Scrapy and Twisted log output is suppressed.
- **URL List Mode (New):** Instead of crawling from a single start URL, you can provide a specific list of URLs. When the TOML configuration contains a non-empty `urlList` (or when multiple URLs are given on the command line), the program processes only those URLs (one per line) and does not follow additional links.
- **Output Metrics:** For each page, the following data is recorded:
  - `url`
  - `title`
  - `linkCount`
  - `controlCount`
  - `byteCount`
  - **`updated`** – the best estimate of the last updated date (YYYY-MM-DD).

## Requirements

- Python 3.13
- [Scrapy](https://scrapy.org/)
- [toml](https://pypi.org/project/toml/)
- [PyInstaller](https://www.pyinstaller.org/) (if creating a standalone executable)

## Installation

1. **Create a Virtual Environment:**

   Open a command prompt, navigate to the project directory, and run:
   ```bash
   python -m venv venv
   venv\Scripts\activate
Install Required Packages:

With the virtual environment activated, run:

bash
Copy
pip install scrapy toml pyinstaller
(Optional) Create a Stand-Alone Executable:

To package the project into a single-file executable for Windows, run:

bash
Copy
pyinstaller --onefile --name getSiteLinks getSiteLinks.py
The executable will be created in the dist folder.

Usage
You can run getSiteLinks either by providing a TOML configuration file or directly via a URL.

Command-Line Options
target:
A TOML configuration file or one or more URLs to crawl.
Note: If multiple URLs are provided (separated by spaces), URL List Mode is used.

--maxLinks:
Maximum number of URLs to crawl (default: 30).

--crawlDepth:
Maximum crawl depth (default: 3).

--parentDir:
Directory filter to restrict crawled URLs (default: empty).

--robotFilter:
Obey the robots.txt file (default: ignore).

--userAgent:
Custom user agent string. This value is added to the pool of random agents used per request.

--log:
Enable logging to a file (default: off). When not enabled, all Scrapy and Twisted log output is suppressed.

Modes
Crawling Mode (Single URL):

bash
Copy
python getSiteLinks.py https://www.example.com --robotFilter --maxLinks 50 --crawlDepth 2 --parentDir /docs --userAgent "CustomUserAgent/1.0" --log
This command starts at the specified URL, obeys robots.txt, limits the crawl to 50 URLs with a depth of 2, filters URLs under /docs, uses a pool of random user agents (including the custom one), and generates a log file alongside the CSV output.

URL List Mode (Multiple URLs):

bash
Copy
python getSiteLinks.py "https://www.example.com/page1" "https://www.example.com/page2" "https://www.example.com/page3"
Alternatively, you can specify a list of URLs via the TOML configuration file by setting urlList to contain one URL per line. In URL List Mode, only the provided URLs are processed and no additional links are followed.

Output
The program generates a CSV file that includes the following columns:

url
title
linkCount
controlCount
byteCount
updated – the best estimated last updated date (YYYY-MM-DD).
Authors
Jamal Mazrui, Consultant, Access Success LLC

License
This project is licensed under the MIT License. See License.html for details. The whole project may be downloaded in a single zip archive from the following address:

<http://GitHub.com/JamalMazrui/getSiteLinks/archive/main.zip>

