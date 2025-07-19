from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import urllib.parse
import re

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def configure_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=en-IN")
    chrome_options.add_argument("--country=IN")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize WebDriver: {str(e)}")
        raise

def extract_indian_price(price_text):
    try:
        price_text = price_text.replace(',', '').replace('₹', '').replace('Rs', '').strip()
        price_match = re.search(r'(\d+\.?\d*)', price_text)
        if price_match:
            return float(price_match.group(1))
        return None
    except:
        return None

def scrape_website(driver, url, selectors, store_name):
    try:
        driver.get(url)
        time.sleep(3)
        
        # Scroll to load dynamic content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3)")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2)")
        time.sleep(1)
        
        results = []
        
        for selector in selectors:
            try:
                elements = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                
                for element in elements[:5]:
                    price = extract_indian_price(element.text)
                    if price:
                        link = ""
                        try:
                            link_element = element.find_element(By.XPATH, "./ancestor::a") or \
                                         element.find_element(By.XPATH, "./ancestor::div[contains(@class,'product')]//a")
                            link = link_element.get_attribute('href')
                        except:
                            pass
                        
                        results.append({
                            'price': price,
                            'link': link
                        })
                if results:
                    break
            except Exception as e:
                logger.warning(f"Selector {selector} failed for {store_name}: {str(e)}")
                continue
                
        return results
    
    except Exception as e:
        logger.error(f"Error scraping {store_name}: {str(e)}")
        return []

def fetch_electronics_prices(product_name):
    driver = None
    try:
        driver = configure_driver()
        prices = {}
        
        encoded_name = urllib.parse.quote_plus(product_name)
        
        # Flipkart (Electronics)
        prices["Flipkart"] = scrape_website(
            driver,
            f"https://www.flipkart.com/search?q={encoded_name}&sid=tyy%2C4io",
            ['._30jeq3._1_WHN1', '._1vC4OE', '.price'],
            "Flipkart"
        )
        
        # Amazon India (Electronics)
        prices["Amazon"] = scrape_website(
            driver,
            f"https://www.amazon.in/s?k={encoded_name}&i=electronics",
            ['.a-price-whole', '.a-offscreen'],
            "Amazon"
        )
        
        # Croma (Electronics)
        prices["Croma"] = scrape_website(
            driver,
            f"https://www.croma.com/search/?text={encoded_name}",
            ['.amount', '.product-price'],
            "Croma"
        )
        
        return {k: v for k, v in prices.items() if v}
        
    except Exception as e:
        logger.error(f"Error in fetch_electronics_prices: {str(e)}")
        return {}
    finally:
        if driver:
            driver.quit()

def fetch_fashion_prices(product_name):
    driver = None
    try:
        driver = configure_driver()
        prices = {}
        
        encoded_name = urllib.parse.quote_plus(product_name)
        hyphen_name = product_name.replace(' ', '-')
        
        # Myntra (Fashion)
        prices["Myntra"] = scrape_website(
            driver,
            f"https://www.myntra.com/{hyphen_name}",
            ['.product-discountedPrice', '.product-price'],
            "Myntra"
        )
        
        # Ajio (Fashion)
        prices["Ajio"] = scrape_website(
            driver,
            f"https://www.ajio.com/search/?text={encoded_name}",
            ['.price', '.prod-sp'],
            "Ajio"
        )
        
        # Tira (Fashion)
        prices["Tira"] = scrape_website(
            driver,
            f"https://www.tirabeauty.com/search?text={encoded_name}",
            ['.final-price', '.discounted-price'],
            "Tira"
        )
        
        return {k: v for k, v in prices.items() if v}
        
    except Exception as e:
        logger.error(f"Error in fetch_fashion_prices: {str(e)}")
        return {}
    finally:
        if driver:
            driver.quit()

@app.route('/chart/electronics', methods=['GET'])
def chart_electronics():
    product_name = request.args.get('q', '').strip()
    if not product_name:
        return jsonify({"error": "Please enter a product name"}), 400
    
    try:
        product_prices = fetch_electronics_prices(product_name)
        if not product_prices:
            return jsonify({"error": "No prices found for this product"}), 404
        
        # Prepare optimized chart data for Chart.js
        chart_data = {
            "labels": [],
            "datasets": [{
                "label": "Average Price (₹)",
                "data": [],
                "backgroundColor": [
                    'rgba(54, 162, 235, 0.7)',
                    'rgba(255, 99, 132, 0.7)',
                    'rgba(75, 192, 192, 0.7)'
                ],
                "borderColor": [
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 99, 132, 1)',
                    'rgba(75, 192, 192, 1)'
                ],
                "borderWidth": 1
            }]
        }
        
        for store, prices in product_prices.items():
            if prices:
                chart_data["labels"].append(store)
                avg_price = sum(p['price'] for p in prices) / len(prices)
                chart_data["datasets"][0]["data"].append(round(avg_price, 2))
        
        return jsonify(chart_data)
    except Exception as e:
        logger.error(f"Error in electronics chart: {str(e)}")
        return jsonify({"error": "Failed to generate chart data"}), 500

@app.route('/chart/fashion', methods=['GET'])
def chart_fashion():
    product_name = request.args.get('q', '').strip()
    if not product_name:
        return jsonify({"error": "Please enter a product name"}), 400
    
    try:
        product_prices = fetch_fashion_prices(product_name)
        if not product_prices:
            return jsonify({"error": "No prices found for this product"}), 404
        
        # Prepare optimized chart data for Chart.js
        chart_data = {
            "labels": [],
            "datasets": [{
                "label": "Average Price (₹)",
                "data": [],
                "backgroundColor": [
                    'rgba(153, 102, 255, 0.7)',
                    'rgba(255, 159, 64, 0.7)',
                    'rgba(255, 206, 86, 0.7)'
                ],
                "borderColor": [
                    'rgba(153, 102, 255, 1)',
                    'rgba(255, 159, 64, 1)',
                    'rgba(255, 206, 86, 1)'
                ],
                "borderWidth": 1
            }]
        }
        
        for store, prices in product_prices.items():
            if prices:
                chart_data["labels"].append(store)
                avg_price = sum(p['price'] for p in prices) / len(prices)
                chart_data["datasets"][0]["data"].append(round(avg_price, 2))
        
        return jsonify(chart_data)
    except Exception as e:
        logger.error(f"Error in fashion chart: {str(e)}")
        return jsonify({"error": "Failed to generate chart data"}), 500

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/electronics')
def electronics():
    return render_template('electronics.html')

@app.route('/fashion')
def fashion():
    return render_template('fashion.html')

@app.route('/search/electronics', methods=['GET'])
def search_electronics():
    product_name = request.args.get('q', '').strip()
    if not product_name:
        return jsonify({"error": "Please enter a product name"}), 400
    
    try:
        product_prices = fetch_electronics_prices(product_name)
        if not product_prices:
            return jsonify({"error": "No prices found for this product"}), 404
        return jsonify(product_prices)
    except Exception as e:
        logger.error(f"Error in electronics search: {str(e)}")
        return jsonify({"error": "Failed to fetch prices"}), 500

@app.route('/search/fashion', methods=['GET'])
def search_fashion():
    product_name = request.args.get('q', '').strip()
    if not product_name:
        return jsonify({"error": "Please enter a product name"}), 400
    
    try:
        product_prices = fetch_fashion_prices(product_name)
        if not product_prices:
            return jsonify({"error": "No prices found for this product"}), 404
        return jsonify(product_prices)
    except Exception as e:
        logger.error(f"Error in fashion search: {str(e)}")
        return jsonify({"error": "Failed to fetch prices"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)