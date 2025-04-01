import os
import time
import logging
import traceback
from collections import Counter
import re
import threading
import pandas as pd
import requests
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from urllib.parse import urlparse
import nltk
from nltk.corpus import stopwords
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains


from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(filename="scraper.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# NLTK 
nltk.download("stopwords")
# stop_words = set(stopwords.words("english"))
stop_words = set(stopwords.words("english")) | {"view", "add", "cart", "quick", "load", "original"}


def fetch_html(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def extract_meta_data(url, folder_name):
        soup = fetch_html(url)
        if not soup:
            return
        
        # Extract Title
        title = soup.title.string.strip() if soup.title else "No title found"

        # Extract Meta Tags
        meta_data = []
        meta_data.append(["Title", title])  # Adding title as first row
        
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property")  # Handle both "name" and "property" attributes
            content = meta.get("content", "No content found")
            if name:  # Ensure it's a named meta tag
                meta_data.append([name, content])
        
        # Convert to DataFrame
        df = pd.DataFrame(meta_data, columns=["Meta Tag", "Content"])

        # Ensure folder exists
        os.makedirs(folder_name, exist_ok=True)

        # Save to CSV
        file_path = os.path.join(folder_name, "meta_data.csv")
        df.to_csv(file_path, index=False)

        logging.info(f"Meta data extracted successfully and saved to {file_path}")

def extract_backlinks(url, folder_name):
    try:
        soup = fetch_html(url)
        if not soup:
            return
        links = [a_tag['href'] for a_tag in soup.find_all('a', href=True)]
        parsed_base_url = urlparse(url)
        base_domain = parsed_base_url.netloc
        backlinks = [link for link in links if urlparse(link).netloc and urlparse(link).netloc != base_domain]
        # Ensure folder exists
        os.makedirs(folder_name, exist_ok=True)
        # Save data
        file_path = os.path.join(folder_name, "backlinks.csv")
        df_links = pd.DataFrame(backlinks, columns=['Link'])
        df_links.to_csv(file_path, index=False)
        print(f"External links saved to {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def extract_headings_and_strong_words(url, folder_name):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    # Initialize data list
    data = []

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)

        # Extract all categories
        main_category_elements = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[contains(@class, 'level-1')]/a/span")))

        if not main_category_elements:
            print("No main categories found")
            return
        
        for main_category_element in main_category_elements:
            main_category_name = main_category_element.text.strip()

            #Hover to reveal subcategories
            actions = ActionChains(driver)
            actions.move_to_element(main_category_element).perform()
            time.sleep(2)
        

            #Extract subacategories
            subcategory_elements = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[@class='container_lab_megamenu']//ul[@class='ul-column']/li/a")))
            if subcategory_elements:
                    for subcategory_element in subcategory_elements:
                        subcategory_name = subcategory_element.text.strip()

                        data.append({
                            'Main Category': main_category_name,
                            'Subcategory': subcategory_name
                        })
            else:
                    print(f"No subcategories found for {main_category_name}")
    
    except Exception as e:
        print(f"Error extracting data: {e}")
        print(traceback.format_exc())
     
        # Save data
        if data:
            os.makedirs(folder_name, exist_ok=True)
            df = pd.DataFrame(data)
            df.to_csv(os.path.join(folder_name, "navbar_data.csv"), index=False)
            print(f"Data saved to: {os.path.join(folder_name, 'navbar_data.csv')}")
        else:
            print("No data to save!")

    except Exception as e:
        print(f"Error: {e}")
        print(traceback.format_exc())

    finally:
        driver.quit()

    # ------------------------------- PRODUCT EXTRACTION -----------------------------------------------

    # Re-initialize WebDriver for product scraping
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    time.sleep(5)  # Allow time for the page to load

    # Accept cookies if present
    try:
        cookie_accept = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'AGREE')]")
        cookie_accept.click()
        time.sleep(1)
    except:
        pass

    product_data = []

    # Find all category sections by checking checkbox
    category_sections = driver.find_elements(By.XPATH, "//input[@class, 'pas-shown-by-js')]")

    #Check if it is already checked
    for section in category_sections:
        if not section.is_selected():
        #Click it
            section.click()

    #Wait
    category_sections = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.XPATH, "//input[@class, 'pas-shown-by-js')]")
    ))

    for section in category_sections:
        try:
            # Extract main category name
            try:
                main_category = section.find_element(By.XPATH, ".//h2[contains(@class, 'productName')]").text.strip()
            except:
                main_category = section.find_element(By.XPATH, ".//h2").text.strip()

            print(f"\nScraping main category: {main_category}")

            # Find all products in this category
            products = section.find_elements(By.XPATH, ".//div[contains(@class, 'laberProduct')]")
            print(f"Found {len(products)} products in {main_category}")

            for product in products:
                try:
                    # Product Name
                    try:
                        name = product.find_element(By.XPATH, ".//h2[contains(@class, 'productName')]").text.strip() 
                        if not name:
                            name = product.find_element(By.XPATH, ".//h2").text.strip()
                        name = name.replace('"', "'")
                    except:
                        name = "N/A"

                    # Product Category (brand)
                    try:
                        product_category = product.find_element(By.XPATH, ".//span[contains(@class, 'manufacturer_name')]").text.strip()
                    except:
                        product_category = "N/A"

                    # Prices
                    try:
                        current_price = product.find_element(By.XPATH, ".//span[contains(@class, 'price'])]").text.strip()
                    except:
                        current_price = "N/A"

                    try:
                        original_price = product.find_element(By.XPATH, ".//span[contains(@class, 'regualr_price')]").text.strip()
                        if not original_price:
                            original_price = current_price  # If no sale, original = current
                    except:
                        original_price = current_price

                    # Add to product data
                    product_data.append({
                        'Main Category': main_category,
                        'Subcategory': "N/A",  # Explicitly set to N/A
                        'Product Category': product_category,
                        'Product Name': name,
                        'Current Price': current_price,
                        'Original Price': original_price
                    })

                except Exception as e:
                    print(f"Error processing product in {main_category}: {e}")
                    continue

        except Exception as e:
            print(f"Error processing category section: {e}")
            continue

    driver.quit()

    # Save results
    if product_data:
        os.makedirs(folder_name, exist_ok=True)
        df = pd.DataFrame(product_data)
        df.to_csv(os.path.join(folder_name, "products.csv"), index=False)
        print(f"\nSuccessfully extracted {len(product_data)} products")
        return df
    else:
        print("No products found")
        return None
    
def extract_keywords(url, folder_name):
    soup = fetch_html(url)
    if not soup:
        return
    
    page_text = soup.get_text()
    words = re.findall(r"\b[a-zA-Z]{3,}\b", page_text.lower())
    filtered_words = [word for word in words if word not in stop_words]
    
    common_keywords = Counter(filtered_words).most_common(20)
    
    vectorizer = TfidfVectorizer(stop_words="english", max_features=50, ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform([" ".join(filtered_words)])
    tfidf_keywords = vectorizer.get_feature_names_out()
    
    df_common = pd.DataFrame(common_keywords, columns=["Keyword", "Count"])
    df_common.to_csv(os.path.join(folder_name, "seo_keywords.csv"), index=False)
    
    df_tfidf = pd.DataFrame(tfidf_keywords, columns=["TF-IDF Keywords"])
    df_tfidf.to_csv(os.path.join(folder_name, "tfidf_keywords.csv"), index=False)
    logging.info("Keywords extracted successfully")

if __name__ == "__main__":
    url = input("Enter the website URL: ").strip()
    folder_name = input("Enter the folder name to save data: ").strip()
    os.makedirs(folder_name, exist_ok=True)
    
    threads = [
        threading.Thread(target=extract_meta_data, args=(url, folder_name)),
        threading.Thread(target=extract_headings_and_strong_words, args=(url, folder_name)),
        threading.Thread(target=extract_keywords, args=(url, folder_name)),
        threading.Thread(target=extract_backlinks, args=(url, folder_name)),
    ]
    
    for thread in threads:
        thread.start()
    
    for thread in threads:
        thread.join()
    
    print("completed. Check folder for results")