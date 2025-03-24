#!/usr/bin/env python
# getSiteLinks - A web crawler
# Author: Jamal Mazrui, Consultant, Access Success LLC
# License: MIT License

import argparse, csv, logging, os, random, re, sys, urllib.parse
from datetime import datetime
from email.utils import parsedate_to_datetime

import scrapy
import toml
from scrapy.crawler import CrawlerProcess
from scrapy.utils.log import configure_logging

# Disable Scrapy’s default logging to the console.
configure_logging(install_root_handler=False)
logging.getLogger("scrapy").setLevel(logging.CRITICAL)
logging.getLogger("twisted").setLevel(logging.CRITICAL)

# Global variable to hold our memory log handler (if --log is enabled)
MEM_LOG_HANDLER = None

def parseAndFormatDate(sDate: str) -> str:
    """
    Attempt to parse a date string using several common formats and return it in YYYY-MM-DD format.
    If none of the formats match, return the original string.
    """
    sDate = sDate.strip()
    if not sDate:
        return ""
    lDateFormats = [
        "%m/%d/%Y",       # e.g., 3/18/2025
        "%m-%d-%Y",       # e.g., 03-18-2025
        "%Y-%m-%d",       # e.g., 2025-03-18
        "%d/%m/%Y",       # e.g., 18/03/2025
        "%d-%m-%Y",       # e.g., 18-03-2025
        "%B %d, %Y",      # e.g., March 18, 2025
        "%b %d, %Y",      # e.g., Mar 18, 2025
        "%a, %d %b %Y %H:%M:%S %Z",  # e.g., Tue, 18 Mar 2025 00:00:00 GMT
        "%a, %d %b %Y %H:%M:%S %z",  # e.g., Tue, 18 Mar 2025 00:00:00 +0000
        "%Y-%m-%dT%H:%M:%S%z",       # e.g., 2025-03-18T12:34:56+0000
        "%Y-%m-%dT%H:%M:%SZ",         # e.g., 2025-03-18T12:34:56Z
    ]
    for sFmt in lDateFormats:
        try:
            dtDate = datetime.strptime(sDate, sFmt)
            return dtDate.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return sDate  # Return the original value if no format matches.

class memoryLogHandler(logging.Handler):
    """A logging handler that stores log messages in memory."""
    def __init__(self) -> None:
        super().__init__()
        self.lLogRecords = []  # list of log messages
    def emit(self, record: logging.LogRecord) -> None:
        sMsg: str = self.format(record)
        self.lLogRecords.append(sMsg)

class randomUserAgentMiddleware:
    """
    Downloader middleware that sets a random User-Agent header for each request.
    It uses a default list of common user agents, and if the configuration provides
    a custom user agent, that value is added to the list.
    """
    def __init__(self, lUserAgents: list) -> None:
        self.lUserAgents = lUserAgents

    @classmethod
    def from_crawler(cls, crawler: scrapy.crawler.Crawler):
        lDefaultAgents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Mobile/15E148 Safari/604.1"
        ]
        sCustomAgent = crawler.settings.get("CUSTOM_USER_AGENT")
        if sCustomAgent and sCustomAgent not in lDefaultAgents:
            lDefaultAgents.append(sCustomAgent)
        return cls(lDefaultAgents)

    def process_request(self, request: scrapy.http.Request, spider: scrapy.Spider) -> None:
        request.headers["User-Agent"] = random.choice(self.lUserAgents)

class spiderCustom(scrapy.Spider):
    """
    A Scrapy spider that crawls a website starting from a given URL or a specific list of URLs,
    collects page metrics, and writes the results to a CSV file.

    Metrics gathered for each page:
      - url: The page URL.
      - title: The page title.
      - linkCount: Number of unique <a> tags with an href attribute.
      - controlCount: Number of elements with a non-empty ARIA role or native HTML controls.
      - byteCount: The byte size of the HTML content.
      - updated: Estimated last updated date (YYYY-MM-DD) derived from HTTP headers or meta tags.

    In crawl mode (when a startUrl is provided), the spider prints one line:
      Crawling <final startUrl>
    as the very first console output. Then, for every page processed (starting with the startUrl),
    the page title is printed on a new line.
    """
    name = "spiderCustom"
    custom_settings = {
        "DEPTH_LIMIT": 3,
        "DOWNLOAD_DELAY": 1,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "DOWNLOADER_MIDDLEWARES": {
            "__main__.randomUserAgentMiddleware": 400,
        },
    }

    def __init__(self, dConfigData: dict, *args: any, **kwargs: any) -> None:
        super().__init__(*args, **kwargs)
        self.dConfigData = dConfigData
        self.iMaxUrls = dConfigData.get("maxUrls", 30)
        self.iCrawlDepth = dConfigData.get("crawlDepth", 3)
        self.sParentDir = dConfigData.get("parentDir", "")
        self.custom_settings["DEPTH_LIMIT"] = self.iCrawlDepth
        self.custom_settings["ROBOTSTXT_OBEY"] = dConfigData.get("robotFilter", False)
        if "userAgent" in dConfigData:
            self.custom_settings["CUSTOM_USER_AGENT"] = dConfigData["userAgent"]

        self.lItems = []         # list of dictionaries with page data
        self.sStartTitle = ""    # will store the title from the first processed page

        # Always initialize the set of processed URLs.
        self.lUrlSet = set()

        # Determine if URL list mode is active.
        self.bUrlListMode = bool(dConfigData.get("urlList", "").strip())
        if self.bUrlListMode:
            self.lUrlList = list(set([sUrl.strip() for sUrl in dConfigData.get("urlList", "").splitlines() if sUrl.strip()]))
        else:
            self.sStartUrl = dConfigData.get("startUrl")
            parseResult = urllib.parse.urlparse(self.sStartUrl)
            sDomain: str = parseResult.netloc
            if sDomain.startswith("www."):
                sDomain = sDomain[4:]
            self.allowed_domains = [sDomain]
        self.bPrintedCrawlingMessage = False  # flag to ensure the "Crawling ..." message is printed only once

    def startRequests(self) -> scrapy.Spider:
        if self.bUrlListMode:
            for sUrl in self.lUrlList:
                if sUrl not in self.lUrlSet:
                    self.lUrlSet.add(sUrl)
                    yield scrapy.Request(url=sUrl, callback=self.parse, dont_filter=True)
        else:
            if self.sStartUrl not in self.lUrlSet:
                self.lUrlSet.add(self.sStartUrl)
            yield scrapy.Request(url=self.sStartUrl, callback=self.parse)
    start_requests = startRequests

    def parse(self, response: scrapy.http.Response) -> any:
        sUrl = response.url
        sTitle = response.xpath("//title/text()").get() or ""
        if not self.bUrlListMode and not self.bPrintedCrawlingMessage:
            print(f"Crawling {sUrl}")
            self.bPrintedCrawlingMessage = True
        if not self.sStartTitle:
            self.sStartTitle = sTitle
        print(sTitle)
        lHrefSet = set()
        for selector in response.xpath("//a[@href]"):
            sHref = selector.xpath("./@href").get()
            sAbsUrl = response.urljoin(sHref)
            lHrefSet.add(sAbsUrl)
        iLinkCount = len(lHrefSet)
        iControlCount = len(response.xpath("//*[(@role and normalize-space(@role) != '') or self::button or self::input or self::select or self::textarea]"))
        iByteCount = len(response.body)
        sUpdatedDate = ""
        if b"Last-Modified" in response.headers:
            try:
                dtLast = parsedate_to_datetime(response.headers[b"Last-Modified"].decode("utf-8"))
                sUpdatedDate = dtLast.strftime("%Y-%m-%d")
            except Exception:
                sUpdatedDate = ""
        if not sUpdatedDate:
            sMeta = response.xpath("//meta[@name='last-modified']/@content").get() or ""
            if sMeta:
                sUpdatedDate = parseAndFormatDate(sMeta)
            if not sUpdatedDate:
                sMeta = response.xpath("//meta[@property='article:modified_time']/@content").get() or ""
                if sMeta:
                    sUpdatedDate = parseAndFormatDate(sMeta)
            if not sUpdatedDate:
                sMeta = response.xpath("//meta[@name='last_modified']/@content").get() or ""
                if sMeta:
                    sUpdatedDate = parseAndFormatDate(sMeta)
            if not sUpdatedDate:
                sMeta = response.xpath("//meta[@name='modified']/@content").get() or ""
                if sMeta:
                    sUpdatedDate = parseAndFormatDate(sMeta)
        dItem = {
            "url": sUrl,
            "title": sTitle,
            "linkCount": iLinkCount,
            "controlCount": iControlCount,
            "byteCount": iByteCount,
            "updated": sUpdatedDate
        }
        self.lItems.append(dItem)
        yield dItem
        if not self.bUrlListMode:
            if len(self.lUrlSet) < self.iMaxUrls:
                for sNextUrl in lHrefSet:
                    if self.sParentDir and not urllib.parse.urlparse(sNextUrl).path.startswith(self.sParentDir):
                        continue
                    if sNextUrl in self.lUrlSet:
                        continue
                    self.lUrlSet.add(sNextUrl)
                    yield scrapy.Request(url=sNextUrl, callback=self.parse)
            else:
                logging.error(f"Reached maximum URL count: {self.iMaxUrls}")

    def closed(self, sReason: str) -> None:
        sRootName = self.sStartTitle.strip() if self.sStartTitle.strip() else "output"
        sSanitized = re.sub(r'[\\\/:*?"<>|]', "", sRootName)
        sCsvRoot = sSanitized
        sCsvFile = f"{sCsvRoot}.csv"
        iSuffix = 1
        while os.path.exists(sCsvFile):
            sCsvFile = f"{sCsvRoot}-{iSuffix:02d}.csv"
            iSuffix += 1
        try:
            with open(sCsvFile, "w", newline="", encoding="utf-8-sig") as fCsv:
                csvWriter = csv.DictWriter(fCsv, fieldnames=["url", "title", "linkCount", "controlCount", "byteCount", "updated"])
                csvWriter.writeheader()
                for dItem in self.lItems:
                    csvWriter.writerow(dItem)
        except Exception as exc:
            logging.error(f"Failed to write CSV file: {exc}")
            return
        if self.dConfigData.get("log", False) and MEM_LOG_HANDLER is not None:
            sLogFile = f"{sCsvRoot}.log"
            try:
                with open(sLogFile, "w", encoding="utf-8-sig") as fLog:
                    for sMsg in MEM_LOG_HANDLER.lLogRecords:
                        fLog.write(f"{sMsg}\n")
            except Exception as exc:
                logging.error(f"Failed to write log file: {exc}")
        print(f"Saved {len(self.lItems)} links to {sCsvFile}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Spider program using Scrapy to crawl a website and produce a CSV report. "
                    "Provide either a TOML configuration file, a single URL, or multiple URLs. "
                    "Optional parameters: --maxLinks, --crawlDepth, --parentDir, --robotFilter, --userAgent, and --log."
    )
    parser.add_argument("target", nargs="+", type=str,
                        help="TOML config file or URL(s) to crawl. Provide multiple URLs (separated by spaces) to use URL List mode.")
    parser.add_argument("--maxLinks", type=int, help="Maximum number of URLs to crawl (default: 30)")
    parser.add_argument("--crawlDepth", type=int, help="Maximum crawl depth (default: 3)")
    parser.add_argument("--parentDir", type=str, help="Directory filter (default: empty)")
    parser.add_argument("--robotFilter", action="store_true", help="Obey robots.txt (default: ignore)")
    parser.add_argument("--userAgent", type=str, help="Custom user agent string (added to random selection pool)")
    parser.add_argument("--log", action="store_true", help="Enable logging to a file (default: off)")
    oArgs = parser.parse_args()

    if os.path.isfile(oArgs.target[0]):
        sTargetFile = oArgs.target[0]
        try:
            with open(sTargetFile, "r", encoding="utf-8-sig") as fToml:
                dConfigData = toml.load(fToml)
        except Exception as exc:
            logging.error(f"Failed to load TOML config file: {exc}")
            sys.exit(1)
    else:
        if len(oArgs.target) > 1:
            dConfigData = {
                "urlList": "\n".join(oArgs.target),
                "maxUrls": 30,
                "crawlDepth": 3,
                "parentDir": "",
                "robotFilter": False,
                "log": False
            }
        else:
            sTarget = oArgs.target[0]
            if sTarget.lower().startswith("www."):
                sTarget = f"http://{sTarget}"
            dConfigData = {
                "startUrl": sTarget,
                "maxUrls": 30,
                "crawlDepth": 3,
                "parentDir": "",
                "robotFilter": False,
                "log": False
            }
    if oArgs.maxLinks is not None:
        dConfigData["maxUrls"] = oArgs.maxLinks
    if oArgs.crawlDepth is not None:
        dConfigData["crawlDepth"] = oArgs.crawlDepth
    if oArgs.parentDir is not None:
        dConfigData["parentDir"] = oArgs.parentDir
    if oArgs.robotFilter:
        dConfigData["robotFilter"] = True
    if oArgs.userAgent is not None:
        dConfigData["userAgent"] = oArgs.userAgent
    if oArgs.log:
        dConfigData["log"] = True

    if not dConfigData.get("log", False):
        logging.disable(logging.CRITICAL)

    oCrawlerProcess = CrawlerProcess()
    oCrawlerProcess.crawl(spiderCustom, dConfigData=dConfigData)
    oCrawlerProcess.start()

if __name__ == "__main__":
    main()
