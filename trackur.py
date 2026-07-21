import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_price(url):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox') # Required for CI/CD environments
    options.add_argument('--disable-dev-shm-usage') # Overcomes limited RAM in Linux containers
    options.add_argument('--disable-gpu')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(url)
        # Replace 'actual-price-class' with the actual class from Bookswagon
        price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "originalprice"))
        )
        # Clean and convert to float
        return float(price_element.text.replace('₹', '').replace(',', '').strip())
    except Exception as e:
        print(f"Error extracting price: {e}")
        return None
    finally:
        driver.quit()

if __name__ == "__main__":
    BOOK_URL = "https://www.bookswagon.com/book/golden-son-pierce-brown/9781444759037"

    # Pull the target price from environment variables (configured in Step 4)
    TARGET_PRICE = float(os.getenv("TARGET_PRICE", 500.0))
    NOTIFY_TOPIC = os.getenv("NOTIFY_TOPIC") 
    
    current_price = get_price(BOOK_URL)
    print(f"Current price: ₹{current_price}")
    
    if current_price and current_price <= TARGET_PRICE:
        print("Price dropped! Sending notification...")
        requests.post(f"https://ntfy.sh/{NOTIFY_TOPIC}", 
            data=f"Price Drop Alert! The book is now ₹{current_price}".encode(encoding='utf-8'),
            headers={"Title": "Bookswagon Tracker"}
        )