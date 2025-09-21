# scrapers.py - Playwright implementation for reliable grocery price scraping
import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import re
import json
import time
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProductData:
    """Data class for product information"""
    name: str
    price: Optional[float]
    mrp: Optional[float]
    quantity: str
    available: bool
    store: str
    search_term: str
    product_url: Optional[str] = None
    image_url: Optional[str] = None


class PlaywrightGroceryScraper:
    """Advanced grocery price scraper using Playwright"""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

        # Store configurations with updated selectors based on current website structures
        self.store_configs = {
            "Blinkit": {
                "base_url": "https://blinkit.com",
                "search_url": "https://blinkit.com/s/?q={query}",
                "selectors": {
                    "location_input": "input[placeholder*='search delivery location'], input[placeholder*='delivery'], input[placeholder*='location'], input[data-testid*='location']",
                    "location_suggestions": "div:has-text('Mumbai Central'), div:has-text('Mumbai'), div[class*='suggestion'], li[role='option']",
                    "first_suggestion": "div:has-text('Central'):first-child, div[class*='suggestion']:first-child, li:first-child",
                    "location_submit": "button:has-text('Detect my location'), button[data-testid*='location'], button:has-text('Set Location')",
                    "search_input": "input[placeholder*='Search'], input[data-testid*='search']",
                    "products": "div[data-testid='plp-product'], div[class*='ProductCard'], div[class*='Product__'], article, .grid > div, div[class*='product-card']",
                    "product_name": "h3, h4, div[class*='ProductName'], div[class*='product-name'], .title, p[class*='name']",
                    "product_price": "div[class*='Price'], span[class*='price'], div[class*='offer-price'], .current-price",
                    "product_mrp": "div[class*='Mrp'], span[class*='mrp'], .original-price, .strikethrough",
                    "product_quantity": "div[class*='Quantity'], span[class*='quantity'], .size, .weight",
                    "out_of_stock": ".out-of-stock, [data-testid*='out-of-stock'], .unavailable, .sold-out",
                    "load_more": "button:has-text('Load More'), .load-more, [data-testid*='load-more']"
                }
            },
            "Instamart": {
                "base_url": "https://www.swiggy.com/instamart",
                "search_url": "https://www.swiggy.com/instamart/search?custom_back=true&query={query}",
                "selectors": {
                    "location_input": "input[placeholder*='location'], .AddressSelector input, input[data-testid*='address']",
                    "search_input": "input[placeholder*='Search'], [data-testid*='search'], .search-input",
                    "products": "div[data-testid*='product'], div[class*='ProductCard'], div[class*='item-card'], article, .grid > div, div[class*='sc-']",
                    "product_name": "h3, h4, div[class*='ProductName'], div[class*='product-name'], div[class*='item-name'], p[class*='name']",
                    "product_price": "div[class*='Price'], span[class*='price'], div[class*='current-price'], span[class*='amount']",
                    "product_mrp": "div[class*='Mrp'], span[class*='mrp'], .original-price, .strikethrough, span[class*='strike']",
                    "product_quantity": "div[class*='Quantity'], span[class*='quantity'], .size, .weight",
                    "out_of_stock": ".out-of-stock, .unavailable, [data-testid*='out-of-stock'], .sold-out",
                    "infinite_scroll": ".load-more, [data-testid*='load-more'], .infinite-scroll-trigger"
                }
            },
            "Zepto": {
                "base_url": "https://www.zeptonow.com",
                "search_url": "https://www.zeptonow.com/search?query={query}",
                "selectors": {
                    "location_input": "input[placeholder*='location'], .location-input, input[data-testid*='location']",
                    "search_input": "input[placeholder*='Search'], [data-testid*='search'], .search-input",
                    "products": "div[data-testid*='product'], div[class*='ProductCard'], div[class*='product-item'], article, .grid > div, div[class*='item-card']",
                    "product_name": "h3, h4, div[class*='ProductName'], div[class*='product-name'], div[class*='item-name'], p[class*='name']",
                    "product_price": "div[class*='Price'], span[class*='price'], div[class*='current-price'], span[class*='amount']",
                    "product_mrp": "div[class*='Mrp'], span[class*='mrp'], .original-price, .strikethrough",
                    "product_quantity": "div[class*='Quantity'], span[class*='quantity'], .size, .weight",
                    "out_of_stock": ".out-of-stock, [data-testid*='out-of-stock'], .unavailable, .sold-out"
                }
            }
        }

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def initialize_browser(self):
        """Initialize Playwright browser with stealth settings to avoid detection"""
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Change to non-headless to avoid detection
            slow_mo=50,      # Add slight delay between actions
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--no-first-run",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--start-maximized",
                "--disable-infobars",
                "--disable-notifications"
            ]
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1366, "height": 768},  # More common viewport size
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            geolocation={"latitude": 19.0760, "longitude": 72.8777},
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document"
            }
        )

        # Add stealth scripts to avoid detection
        await self.context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock languages and plugins
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'hi'],
            });
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        # Less aggressive resource blocking - only block tracking/analytics
        await self.context.route("**/*", self._handle_route_minimal)

    async def _handle_route_minimal(self, route, request):
        """Minimal request handling - only block tracking/analytics, not essential resources"""
        # Only block tracking and analytics to avoid breaking the page
        blocked_domains = [
            "googletagmanager.com",
            "google-analytics.com",
            "facebook.com/tr",
            "doubleclick.net",
            "amazon-adsystem.com",
            "googlesyndication.com"
        ]

        # Block only specific tracking resources
        if any(domain in request.url for domain in blocked_domains):
            await route.abort()
        else:
            await route.continue_()

    async def scrape_store_products(self, store_name: str, search_term: str, location: str = "Mumbai") -> List[ProductData]:
        """Scrape products with enhanced error handling and retries"""

        if store_name not in self.store_configs:
            logger.error(f"Store {store_name} not configured")
            return []

        config = self.store_configs[store_name]
        products = []
        max_retries = 2

        for attempt in range(max_retries):
            page = None
            try:
                page = await self.context.new_page()

                # Set shorter timeouts to prevent hanging
                page.set_default_timeout(20000)
                page.set_default_navigation_timeout(30000)

                page.on("console", lambda msg: logger.info(f"Console {store_name}: {msg.text}"))

                # Add connection error handling
                page.on("response", lambda response: logger.warning(f"Failed response {store_name}: {response.status}") if response.status >= 400 else None)

                await self._setup_store_location(page, store_name, location, config)
                await self._perform_search(page, search_term, config)
                await self._wait_for_products(page, config)

                if store_name == "Instamart":
                    await self._handle_infinite_scroll(page, config)

                products = await self._extract_products(page, search_term, store_name, config)

                if products or attempt == max_retries - 1:
                    break

                logger.info(f"Retry {attempt + 1} for {store_name}")
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed for {store_name}: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error(f"All attempts failed for {store_name}")
            finally:
                if page:
                    try:
                        await page.close()
                    except:
                        pass

        logger.info(f"Successfully scraped {len(products)} products from {store_name}")
        return products

    async def _setup_store_location(self, page: Page, store_name: str, location: str, config: dict):
        """Enhanced location setup with better Blinkit handling"""
        try:
            logger.info(f"Navigating to {store_name} base URL: {config['base_url']}")
            await page.goto(config["base_url"], wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)
            
            # Handle popups/cookie banners
            await self._handle_popups(page)
            
            location_selector = config["selectors"].get("location_input")
            
            if store_name == "Blinkit":
                await self._handle_blinkit_location(page, location, location_selector)
            elif store_name == "Instamart":
                await self._handle_instamart_location(page, location, config)
            elif store_name == "Zepto":
                await self._handle_zepto_location(page, location, config)
            else:
                logger.info(f"No specific location handling for {store_name}")
                
        except Exception as e:
            logger.error(f"Failed to setup {store_name}: {e}")
            raise

    async def _handle_popups(self, page: Page):
        """Handle various popups and overlays"""
        popup_selectors = [
            "button:has-text('Accept')",
            "button:has-text('Allow')", 
            "button:has-text('Continue')",
            "button:has-text('OK')",
            ".modal-close",
            "[data-testid*='close']",
            ".close-button"
        ]
        
        for selector in popup_selectors:
            try:
                await page.click(selector, timeout=3000)
                logger.info(f"Closed popup with selector: {selector}")
                await asyncio.sleep(1)
                break
            except:
                continue

    async def _handle_blinkit_location(self, page: Page, location: str, location_selector: str):
        """Enhanced Blinkit location handling with multiple strategies"""
        logger.info("Starting Blinkit location setup")
        
        try:
            # Strategy 1: Wait for and interact with location input
            await self._blinkit_location_strategy_1(page, location, location_selector)
        except Exception as e1:
            logger.warning(f"Blinkit Strategy 1 failed: {e1}")
            try:
                # Strategy 2: Alternative selectors and approach
                await self._blinkit_location_strategy_2(page, location)
            except Exception as e2:
                logger.warning(f"Blinkit Strategy 2 failed: {e2}")
                try:
                    # Strategy 3: Direct URL approach
                    await self._blinkit_location_strategy_3(page, location)
                except Exception as e3:
                    logger.error(f"All Blinkit location strategies failed: {e3}")

    async def _blinkit_location_strategy_1(self, page: Page, location: str, location_selector: str):
        """Primary strategy: Standard location input handling"""
        logger.info("Trying Blinkit Strategy 1: Standard location input")
        
        # Enhanced selector list for location input
        location_selectors = [
            location_selector,
            "input[placeholder*='location']",
            "input[placeholder*='delivery']", 
            "input[data-testid*='location']",
            "input[class*='location']",
            "input[class*='address']",
            ".location-input input",
            "[data-testid='location-input']"
        ]
        
        input_element = None
        working_selector = None
        
        # Find working location input
        for selector in location_selectors:
            if not selector:
                continue
            try:
                await page.wait_for_selector(selector, state="visible", timeout=10000)
                input_element = page.locator(selector).first
                # Verify element is actually visible and interactable
                if await input_element.is_visible() and await input_element.is_enabled():
                    working_selector = selector
                    logger.info(f"Found working location input: {selector}")
                    break
            except:
                continue
        
        if not input_element or not working_selector:
            raise Exception("No working location input found")
        
        # Clear and fill location
        logger.info(f"Filling location input with: {location}")
        await input_element.clear()
        await asyncio.sleep(1)
        await input_element.type(location, delay=100)  # Type with delay
        await asyncio.sleep(3)  # Wait for suggestions to load
        
        # Handle location suggestions with multiple approaches
        await self._select_blinkit_suggestion(page, input_element, working_selector)

    async def _select_blinkit_suggestion(self, page: Page, input_element, input_selector: str):
        """Select first location suggestion using multiple methods"""
        logger.info("Attempting to select first location suggestion")
        
        # Method 1: Keyboard navigation (most reliable)
        try:
            logger.info("Method 1: Keyboard navigation")
            await input_element.focus()
            await asyncio.sleep(1)
            await page.keyboard.press("ArrowDown")
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            logger.info("Successfully used keyboard navigation")
            await asyncio.sleep(3)
            return
        except Exception as e:
            logger.warning(f"Keyboard navigation failed: {e}")
        
        # Method 2: Click on suggestion dropdown
        try:
            logger.info("Method 2: Click on suggestion")
            suggestion_selectors = [
                ".suggestions li:first-child",
                ".dropdown-item:first-child", 
                "[data-testid*='suggestion']:first-child",
                ".suggestion:first-child",
                ".location-suggestion:first-child",
                "ul li:first-child",
                "[role='option']:first-child"
            ]
            
            for selector in suggestion_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    await page.click(selector)
                    logger.info(f"Clicked suggestion with: {selector}")
                    await asyncio.sleep(2)
                    return
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"Click suggestion failed: {e}")
        
        # Method 3: Search for clickable elements containing location text
        try:
            logger.info("Method 3: Search for location text elements")
            # Look for elements that might contain location suggestions
            location_elements = await page.locator("text=/.*Mumbai.*/i").all()
            if location_elements:
                await location_elements[0].click()
                logger.info("Clicked on location text element")
                await asyncio.sleep(2)
                return
        except Exception as e:
            logger.warning(f"Location text element click failed: {e}")
        
        # Method 4: Just press Enter on input (fallback)
        try:
            logger.info("Method 4: Fallback - Press Enter")
            await input_element.focus()
            await page.keyboard.press("Enter")
            logger.info("Pressed Enter as fallback")
            await asyncio.sleep(3)
        except Exception as e:
            logger.warning(f"Enter fallback failed: {e}")

    async def _blinkit_location_strategy_2(self, page: Page, location: str):
        """Alternative strategy: Try different page elements"""
        logger.info("Trying Blinkit Strategy 2: Alternative elements")
        
        # Look for location buttons or alternative inputs
        alt_selectors = [
            ".location-button",
            "[data-testid='location-button']",
            "[data-testid*='change-location']",
            ".address-selector"
        ]
        
        for selector in alt_selectors:
            try:
                await page.click(selector, timeout=5000)
                logger.info(f"Clicked alternative location selector: {selector}")
                await asyncio.sleep(2)
                
                # Now try to find input again
                input_selectors = [
                    "input[placeholder*='location']",
                    "input[placeholder*='address']",
                    "input[type='text']"
                ]
                
                for input_sel in input_selectors:
                    try:
                        await page.fill(input_sel, location)
                        await asyncio.sleep(2)
                        await page.keyboard.press("ArrowDown")
                        await page.keyboard.press("Enter")
                        logger.info("Successfully filled alternative input")
                        return
                    except:
                        continue
                        
            except:
                continue
        
        raise Exception("Strategy 2 failed - no alternative elements found")

    async def _blinkit_location_strategy_3(self, page: Page, location: str):
        """Last resort: Try to navigate with location in URL"""
        logger.info("Trying Blinkit Strategy 3: URL approach")
        
        # Some grocery apps allow location in URL parameters
        location_encoded = location.replace(" ", "%20")
        url_variants = [
            f"https://blinkit.com/?location={location_encoded}",
            f"https://blinkit.com/search?location={location_encoded}",
            f"https://blinkit.com/{location_encoded.lower()}"
        ]
        
        for url in url_variants:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                
                # Check if location was set by looking for location text on page
                page_content = await page.content()
                if location.lower() in page_content.lower():
                    logger.info(f"Successfully set location via URL: {url}")
                    return
            except:
                continue
        
        raise Exception("Strategy 3 failed - URL approach unsuccessful")

    async def _handle_instamart_location(self, page: Page, location: str, config: dict):
        """Enhanced Instamart location handling"""
        logger.info("Setting up Instamart location")
        location_selector = config["selectors"].get("location_input")
        
        if not location_selector:
            logger.info("No location selector for Instamart")
            return
        
        try:
            await page.wait_for_selector(location_selector, state="visible", timeout=15000)
            await page.fill(location_selector, location)
            await asyncio.sleep(2)
            
            # Try keyboard navigation for suggestions
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)
            
            # Try submit button if available
            submit_selector = config["selectors"].get("location_submit")
            if submit_selector:
                try:
                    await page.click(submit_selector, timeout=5000)
                    await asyncio.sleep(2)
                except:
                    logger.info("Submit button not needed or not found")
                    
            logger.info("Instamart location setup completed")
            
        except Exception as e:
            logger.warning(f"Instamart location setup failed: {e}")

    async def _handle_zepto_location(self, page: Page, location: str, config: dict):
        """Enhanced Zepto location handling"""
        logger.info("Setting up Zepto location")
        location_selector = config["selectors"].get("location_input")
        
        if not location_selector:
            logger.info("No location selector for Zepto")
            return
        
        try:
            await page.wait_for_selector(location_selector, state="visible", timeout=15000)
            await page.fill(location_selector, location)
            await asyncio.sleep(2)
            
            # Handle suggestions
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)
            
            logger.info("Zepto location setup completed")
            
        except Exception as e:
            logger.warning(f"Zepto location setup failed: {e}")

    async def _debug_blinkit_page_state(self, page: Page, stage: str):
        """Debug helper to understand page state"""
        try:
            # Take screenshot
            await page.screenshot(path=f"debug_blinkit_{stage}_{int(time.time())}.png")
            
            # Log current URL
            current_url = page.url
            logger.info(f"Debug {stage} - Current URL: {current_url}")
            
            # Log visible input elements
            inputs = await page.locator("input").all()
            logger.info(f"Debug {stage} - Found {len(inputs)} input elements")
            
            for i, inp in enumerate(inputs[:5]):  # Log first 5 inputs
                try:
                    placeholder = await inp.get_attribute("placeholder")
                    class_name = await inp.get_attribute("class")
                    is_visible = await inp.is_visible()
                    logger.info(f"  Input {i}: placeholder='{placeholder}', class='{class_name}', visible={is_visible}")
                except:
                    pass
                    
            # Log any error messages on page
            error_elements = await page.locator(".error, .alert, .warning").all()
            for error in error_elements:
                try:
                    error_text = await error.inner_text()
                    logger.warning(f"Page error: {error_text}")
                except:
                    pass
                    
        except Exception as e:
            logger.warning(f"Debug failed: {e}")

    async def _perform_search(self, page: Page, search_term: str, config: dict):
        """Perform search on the store"""
        try:
            # Try direct URL navigation first
            search_url = config["search_url"].format(query=search_term.replace(" ", "%20"))
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

        except Exception as e:
            logger.warning(f"Direct search failed, trying search input: {e}")

            # Fallback to search input
            search_selector = config["selectors"].get("search_input")
            if search_selector:
                await page.wait_for_selector(search_selector, timeout=10000)
                await page.fill(search_selector, search_term)
                await page.press(search_selector, "Enter")
                await asyncio.sleep(3)

    async def _wait_for_products(self, page: Page, config: dict):
        """Wait for products to load with comprehensive selector attempts"""
        product_selector = config["selectors"]["products"]

        logger.info(f"Waiting for products with selectors: {product_selector}")

        # Try each selector individually and log results
        selectors = [s.strip() for s in product_selector.split(", ")]

        found_products = False
        working_selector = None

        for selector in selectors:
            try:
                elements = await page.locator(selector).all()
                logger.info(f"Selector '{selector}': Found {len(elements)} elements")
                if elements:
                    await page.wait_for_selector(selector, timeout=10000, state="visible")
                    found_products = True
                    working_selector = selector
                    logger.info(f"Successfully found products with selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}")
                continue

        if found_products:
            # Update the config with working selector for this session
            config["selectors"]["products"] = working_selector
            logger.info(f"Using working selector: {working_selector}")

            # Wait for content to stabilize
            await asyncio.sleep(3)
            await page.wait_for_load_state("networkidle", timeout=15000)
        else:
            logger.warning("No product elements found with any selector")

            # Take a screenshot for debugging
            try:
                await page.screenshot(path=f"debug_no_products_{int(time.time())}.png")
                logger.info("Debug screenshot saved")
            except:
                pass

    async def _handle_infinite_scroll(self, page: Page, config: dict):
        """Handle infinite scroll for Instamart"""
        try:
            scroll_selector = config["selectors"].get("infinite_scroll")
            if not scroll_selector:
                return

            max_scrolls = 5
            scroll_count = 0

            while scroll_count < max_scrolls:
                # Check for load more elements
                load_more_elements = await page.locator(scroll_selector).all()

                if not load_more_elements:
                    break

                # Scroll the load more element into view
                try:
                    await load_more_elements[0].scroll_into_view_if_needed()
                    await asyncio.sleep(2)

                    # Check if more products loaded
                    new_load_more = await page.locator(scroll_selector).all()
                    if len(new_load_more) == len(load_more_elements):
                        break

                except Exception as e:
                    logger.info(f"Scroll handling completed: {e}")
                    break

                scroll_count += 1

            logger.info(f"Completed {scroll_count} scroll operations")

        except Exception as e:
            logger.warning(f"Infinite scroll handling failed: {e}")

    async def _extract_products(self, page: Page, search_term: str, store_name: str, config: dict) -> List[ProductData]:
        """Extract product data with enhanced fallback logic"""
        products = []

        try:
            # Get all product elements
            product_elements = await page.locator(config["selectors"]["products"]).all()
            logger.info(f"Found {len(product_elements)} product elements in {store_name}")
            
            # Debug: log HTML of first 3 product elements
            for el in product_elements[:3]:
                try:
                    html = await el.inner_html()
                    logger.info(f"Product HTML: {html[:200]}")
                except Exception as e:
                    logger.warning(f"Failed to get product HTML: {e}")

            if len(product_elements) == 0:
                logger.warning(f"No product elements found in {store_name}")
                return products

            # Limit to first 15 products for performance
            for i, element in enumerate(product_elements[:15]):
                try:
                    # Extract product data using enhanced helper methods
                    name = await self._extract_text_from_element_enhanced(element, config["selectors"].get("product_name", ""), store_name)
                    price_text = await self._extract_text_from_element_enhanced(element, config["selectors"].get("product_price", ""), store_name)
                    mrp_text = await self._extract_text_from_element_enhanced(element, config["selectors"].get("product_mrp", ""), store_name)
                    quantity = await self._extract_text_from_element_enhanced(element, config["selectors"].get("product_quantity", ""), store_name)

                    # If no name found, try generic selectors
                    if not name:
                        name = await self._extract_text_generic(element, ["h1", "h2", "h3", "h4", "h5", "h6", ".title", ".name"])

                    # If no price found, try generic price selectors
                    if not price_text:
                        price_text = await self._extract_text_generic(element, ["*:has-text('₹')", "[class*='price']", "[class*='Price']", "[class*='amount']"])

                    # Parse prices
                    price = self._parse_price(price_text)
                    mrp = self._parse_price(mrp_text)

                    # Check availability
                    out_of_stock_elements = await element.locator(config["selectors"].get("out_of_stock", "")).all()
                    available = len(out_of_stock_elements) == 0

                    # Get product URL if possible
                    product_url = await self._extract_product_url(element, store_name)

                    # Log extraction details for debugging
                    logger.debug(f"Product {i}: name='{name}', price_text='{price_text}', price={price}")

                    # More relaxed criteria - accept products with name OR price
                    if (name and name.strip()) or (price is not None):
                        # If no name, use a generic description
                        if not name or not name.strip():
                            name = f"Product from {store_name}"

                        product = ProductData(
                            name=name.strip(),
                            price=price,
                            mrp=mrp,
                            quantity=quantity.strip() if quantity else "",
                            available=available,
                            store=store_name,
                            search_term=search_term,
                            product_url=product_url
                        )
                        products.append(product)

                        logger.info(f"Extracted: {name} - ₹{price} from {store_name}")

                except Exception as e:
                    logger.warning(f"Failed to extract product {i} from {store_name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Product extraction failed for {store_name}: {e}")

        return products

    async def _extract_text_from_element_enhanced(self, element, selectors: str, store_name: str) -> str:
        """Enhanced text extraction with better fallbacks"""
        if not selectors:
            return ""

        for selector in selectors.split(", "):
            try:
                selector = selector.strip()
                text_elements = await element.locator(selector).all()

                for text_element in text_elements:
                    try:
                        text = await text_element.inner_text()
                        if text and text.strip() and len(text.strip()) > 1:
                            return text.strip()
                    except:
                        continue

            except Exception as e:
                logger.debug(f"Selector '{selector}' failed for {store_name}: {e}")
                continue
        return ""

    async def _extract_text_generic(self, element, selectors: List[str]) -> str:
        """Generic text extraction for fallback scenarios"""
        for selector in selectors:
            try:
                text_elements = await element.locator(selector).all()
                for text_element in text_elements:
                    try:
                        text = await text_element.inner_text()
                        if text and text.strip() and len(text.strip()) > 1:
                            return text.strip()
                    except:
                        continue
            except:
                continue
        return ""

    async def _extract_product_url(self, element, store_name: str) -> Optional[str]:
        """Extract product URL with fallbacks"""
        try:
            # Try different link selectors
            link_selectors = ["a", "[href]", "a[href]"]

            for selector in link_selectors:
                try:
                    link_elements = await element.locator(selector).all()
                    for link_element in link_elements:
                        href = await link_element.get_attribute("href")
                        if href and ("/product" in href or "/item" in href or len(href) > 10):
                            if not href.startswith("http"):
                                href = f"{self.store_configs[store_name]['base_url']}{href}"
                            return href
                except:
                    continue
        except:
            pass
        return None

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price from text string"""
        if not price_text:
            return None

        # Remove currency symbols and extract numbers
        price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', '').replace('₹', ''))
        if price_match:
            try:
                return float(price_match.group().replace(',', ''))
            except:
                return None
        return None

    def _calculate_similarity_score(self, product_name: str, search_term: str) -> float:
        """Calculate similarity between product name and search term"""
        product_words = set(product_name.lower().split())
        search_words = set(search_term.lower().split())

        if not search_words:
            return 0.0

        # Calculate Jaccard similarity
        intersection = len(product_words.intersection(search_words))
        union = len(product_words.union(search_words))

        return intersection / union if union > 0 else 0

    def _find_best_match(self, products: List[ProductData], search_term: str) -> Optional[ProductData]:
        """Find the best matching product for the search term"""
        if not products:
            return None

        # Filter available products first
        available_products = [p for p in products if p.available]
        if not available_products:
            available_products = products  # Fallback to all products

        # Score products by similarity
        best_product = None
        best_score = 0.0

        for product in available_products:
            score = self._calculate_similarity_score(product.name, search_term)
            if score > best_score:
                best_score = score
                best_product = product

        return best_product or available_products[0]

    async def scrape_all_stores(self, items: List[str], stores: List[str] = None, location: str = "Mumbai") -> Dict[str, Dict[str, Dict]]:
        """Scrape all stores with improved stability"""

        if stores is None:
            stores = list(self.store_configs.keys())

        results = {}
        semaphore = asyncio.Semaphore(2)  # Reduce concurrency to 2

        async def scrape_store_for_item(store: str, item: str):
            async with semaphore:
                try:
                    await asyncio.sleep(random.uniform(1, 3))  # Random delay
                    products = await self.scrape_store_products(store, item, location)
                    best_match = self._find_best_match(products, item)

                    if best_match:
                        return {
                            "price": best_match.price,
                            "available": best_match.available,
                            "name": best_match.name,
                            "quantity": best_match.quantity,
                            "url": best_match.product_url,
                            "mrp": best_match.mrp
                        }
                    else:
                        return {
                            "price": None,
                            "available": False,
                            "name": "",
                            "quantity": "",
                            "url": None,
                            "mrp": None
                        }

                except asyncio.CancelledError:
                    logger.info(f"Scraping cancelled for {store}/{item}")
                    raise
                except Exception as e:
                    logger.error(f"Error scraping {store} for {item}: {e}")
                    return {
                        "price": None,
                        "available": False,
                        "name": "",
                        "quantity": "",
                        "url": None,
                        "mrp": None,
                        "error": str(e)
                    }

        for item in items:
            logger.info(f"Processing item: {item}")

            try:
                tasks = [scrape_store_for_item(store, item) for store in stores]
                store_results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=120  # 2 minute timeout per item
                )

                item_data = {}
                for i, result in enumerate(store_results):
                    store = stores[i]
                    if isinstance(result, Exception):
                        logger.error(f"Exception for {store}/{item}: {result}")
                        item_data[store] = {
                            "price": None,
                            "available": False,
                            "name": "",
                            "quantity": "",
                            "url": None,
                            "mrp": None,
                            "error": str(result)
                        }
                    else:
                        item_data[store] = result

                results[item] = item_data
                await asyncio.sleep(2)  # Longer delay between items

            except asyncio.TimeoutError:
                logger.error(f"Timeout processing item: {item}")
                results[item] = {store: {"price": None, "available": False, "name": "", "quantity": "", "url": None, "mrp": None, "error": "Timeout"} for store in stores}

        return results

    async def close(self):
        """Close browser and cleanup"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()


# Public API functions for integration with existing code
async def fetch_prices_for_list_real(items: List[str], location: str = "Mumbai", stores: List[str] = None) -> Dict:
    """
    Main async function to fetch real prices from grocery stores

    Args:
        items: List of grocery items to search for
        location: City/location for price search
        stores: List of stores to search (default: all available)

    Returns:
        Dictionary with item -> store -> price data
    """
    async with PlaywrightGroceryScraper() as scraper:
        results = await scraper.scrape_all_stores(items, stores, location)

        # Cache results if db module available
        try:
            from db import cache_price
            for item, stores_data in results.items():
                for store, data in stores_data.items():
                    if data.get("price"):
                        cache_price(store, item, data["price"], data.get("available", False))
        except ImportError:
            logger.info("Database caching not available")

        return results


def fetch_prices_for_list_real_sync(items: List[str], location: str = "Mumbai", stores: List[str] = None) -> Dict:
    """Synchronous wrapper with timeout handling"""
    try:
        # Properly run the async function in a new event loop
        return asyncio.run(
            asyncio.wait_for(
                fetch_prices_for_list_real(items, location, stores),
                timeout=300  # 5 minute total timeout
            )
        )
    except asyncio.TimeoutError:
        logger.error("Overall scraping timeout reached")
        return {item: {store: {"price": None, "available": False, "name": "", "quantity": "", "url": None, "mrp": None, "error": "Timeout"} for store in (stores or ["Blinkit", "Instamart", "Zepto"])} for item in items}
    except Exception as e:
        logger.error(f"Sync wrapper error: {e}")
        return {}


# Testing and debugging functions
async def test_single_store(store_name: str, search_term: str, location: str = "Mumbai"):
    """Test scraping a single store"""
    async with PlaywrightGroceryScraper() as scraper:
        products = await scraper.scrape_store_products(store_name, search_term, location)

        print(f"\n=== {store_name} Results for '{search_term}' ===")
        for i, product in enumerate(products[:5], 1):
            print(f"{i}. {product.name}")
            print(f"   Price: ₹{product.price} | Available: {product.available}")
            print(f"   Quantity: {product.quantity}")
            if product.product_url:
                print(f"   URL: {product.product_url}")
            print()


async def test_all_stores(search_term: str = "milk 1l", location: str = "Mumbai"):
    """Test scraping all stores"""
    results = await fetch_prices_for_list_real([search_term], location)

    print(f"\n=== Price Comparison for '{search_term}' ===")
    for item, stores in results.items():
        print(f"\nItem: {item}")
        for store, data in stores.items():
            status = "✅ Available" if data['available'] else "❌ Unavailable"
            price = f"₹{data['price']}" if data['price'] else "N/A"
            print(f"  {store}: {price} {status}")
            if data.get('name'):
                print(f"    Product: {data['name']}")


# Example usage and testing
if __name__ == "__main__":
    # Test single store
    # asyncio.run(test_single_store("Blinkit", "milk 1l"))

    # Test all stores
    asyncio.run(test_all_stores("bread"))

    # Test multiple items
    # test_items = ["milk 1l", "bread", "eggs", "rice 5kg"]
    # results = asyncio.run(fetch_prices_for_list_real(test_items))
    # print(json.dumps(results, indent=2, default=str))