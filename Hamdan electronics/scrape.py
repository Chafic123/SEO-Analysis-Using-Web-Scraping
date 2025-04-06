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
from datetime import datetime


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
            name = meta.get("name") or meta.get("property")
            content = meta.get("content", "No content found")
            if name:
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

        parsed_base_url = urlparse(url)
        base_domain = parsed_base_url.netloc

        backlinks = []
        for a_tag in soup.find_all('a', href=True):
            link_url = a_tag['href']
            link_domain = urlparse(link_url).netloc

            # Skip if internal link or empty domain
            if not link_domain or link_domain == base_domain:
                continue

            # Extract platform name from the title if available
            platform_name = a_tag.get('title', 'Unknown')
            backlinks.append({'Platform': platform_name, 'Link': link_url})

        # Ensure folder exists
        os.makedirs(folder_name, exist_ok=True)

        # Save to CSV
        file_path = os.path.join(folder_name, "backlinks.csv")
        df_links = pd.DataFrame(backlinks)
        df_links.to_csv(file_path, index=False)
        print(f"External links saved to {file_path}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def extract_headings_and_strong_words(url, folder_name):

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized") 
    options.add_argument("--headless")
    
    # Initialize the WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    data = []

    try:
        # Navigate to the URL
        driver.get(url)
        wait = WebDriverWait(driver, 15)

        # Get all top-level menu items
        main_categories = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//ul[@class='menu-content']/li[contains(@class, 'level-1')]/a/span")))
        
        for category in main_categories:
            main_category = category.text.strip()
            if not main_category:
                continue

            # Check if this category has a dropdown by looking for the dropdown icon
            parent_li = category.find_element(By.XPATH, "./ancestor::li")
            has_dropdown = len(parent_li.find_elements(By.XPATH, ".//span[contains(@class, 'icon-drop-mobile')]")) > 0
            
            if has_dropdown:
                # Hover to reveal dropdown menu
                ActionChains(driver).move_to_element(category).perform()
                time.sleep(1) 
                
                try:
                    dropdown = parent_li.find_element(By.XPATH, ".//div[contains(@class, 'lab-sub-menu')]")
                    
                    # Process each column in the dropdown menu
                    columns = dropdown.find_elements(By.XPATH, ".//div[contains(@class, 'lab-menu-col')]")
                    
                    for col in columns:
                        # Get subcategory header
                        try:
                            header = col.find_element(By.XPATH, ".//li[contains(@class, 'item-header')]/a")
                            subcategory = header.text.strip()
                        except:
                            continue
                        
                        # Get all items under this subcategory
                        items = col.find_elements(By.XPATH, ".//li[contains(@class, 'item-line')]/a[normalize-space(text())]")
                        item_list = [item.text.strip() for item in items if item.text.strip()]
                        
                        if subcategory and item_list:
                            data.append({
                                'Main Category': main_category,
                                'Subcategory': subcategory,
                                'Items': ", ".join(item_list)
                            })
                except Exception as e:
                    print(f"Couldn't process dropdown for {main_category}")
                    data.append({
                        'Main Category': main_category,
                        'Subcategory': 'N/A',
                        'Items': 'N/A'
                    })
            else:
                # For categories without dropdowns
                data.append({
                    'Main Category': main_category,
                    'Subcategory': 'N/A',
                    'Items': 'N/A'
                })

        # Save to CSV
        if data:
            # Create DataFrame and save to CSV
            df = pd.DataFrame(data)
            os.makedirs(folder_name, exist_ok=True)
            df.to_csv(os.path.join(folder_name, "navbar.csv"), index=False)
            print("Navbar data extracted successfully")
        else:
            print("No data was collected from the page")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        driver.quit()

        # ------------------------------- PRODUCT EXTRACTION -----------------------------------------------
        
    # Re-initialize WebDriver 
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    time.sleep(5)  


    try:
        cookie_accept = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'AGREE')]")
        cookie_accept.click()
        time.sleep(1)
    except:
        pass

    product_data = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Find all category sections with sliders
    category_sections = driver.find_elements(By.XPATH, "//div[contains(@class, 'laberProdCategory') or contains(@class, 'Lab-featured-prod column')]")

    for section in category_sections:
        try:
            # main category name
            try:
                main_category = section.find_element(By.XPATH, ".//h3//span[contains(@class, 'strong')]").text.strip()
            except:
                main_category = section.find_element(By.XPATH, ".//h3").text.strip()

            print(f"\nScraping main category: {main_category}")

            # Find products ONLY within this section
            products = section.find_elements(By.XPATH, ".//article[contains(@class, 'product-miniature')]")
            print(f"Found {len(products)} products in category: {main_category}")

            for product in products:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", product)
                    time.sleep(0.2)

                    # Product Name
                    try:
                        name = product.find_element(By.XPATH, ".//h2[contains(@class, 'productName')]").text.strip()
                        if not name:
                            name = product.find_element(By.XPATH, ".//h2").text.strip()
                        name = name.replace('"', "'")
                    except:
                        name = "N/A"

                    # Prices
                    try:
                        current_price = product.find_element(By.XPATH, ".//span[@class='price' and @itemprop='price']").text.strip()
                    except:
                        current_price = "N/A"

                    try:
                        original_price = product.find_element(By.XPATH, ".//span[contains(@class, 'regular-price')]").text.strip()
                        if not original_price:
                            original_price = current_price 
                    except:
                        original_price = current_price

                    # Add to product data
                    product_data.append({
                        'Timestamp': timestamp,
                        'Main Category': main_category,
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
    
        df['Product Name'] = df['Product Name'].str.strip()
        df = df[df['Product Name'] != "N/A"]  
    
        df = df.drop_duplicates(subset=['Main Category', 'Product Name'], keep='first')
    
        file_path = os.path.join(folder_name, "products.csv")
    
        if os.path.exists(file_path):
            df.to_csv(file_path, mode='a', header=False, index=False)
        else:
            df.to_csv(file_path, mode='w', header=True, index=False)

    print(f"\nSuccessfully extracted {len(df)} unique products")
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
    # url = input("Enter the website URL: ").strip()
    # folder_name = input("Enter the folder name to save data: ").strip()
    url = "https://hamdanelectronics.com/"
    folder_name = "Hamdan_Csv"
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