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
import nltk
from nltk.corpus import stopwords
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
from urllib.parse import urlparse

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
            
        # Find the footer social media section
        social_section = soup.find('div', class_='footer__column footer--social')
        
        if social_section:
            # Extract all social media links
            social_links = []
            for item in social_section.find_all('li', class_='list-social__item'):
                link = item.find('a', href=True)
                if link:
                    # Get the platform name from visually-hidden span or from URL
                    platform = link.find('span', class_='visually-hidden')
                    platform_name = platform.text.strip() if platform else link['href'].split('.')[1].capitalize()
                    
                    social_links.append({
                        'Platform': platform_name,
                        'URL': link['href']
                    })
            
            whatsapp_chat = soup.find('a', class_='blantershow-chat', href=True)
            if whatsapp_chat:
                social_links.append({
                    'Platform': 'WhatsApp',
                    'URL': whatsapp_chat['href']
                })
            
            # Ensure folder exists
            os.makedirs(folder_name, exist_ok=True)
            
            # Save data
            file_path = os.path.join(folder_name, "backlinks.csv")
            df_links = pd.DataFrame(social_links)
            df_links.to_csv(file_path, index=False)
            print(f"Social media links saved to {file_path}")
            
            return df_links
        else:
            print("No social media section found in footer")
            return None
            
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def extract_headings_and_strong_words(url, folder_name):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless") 
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    data = []

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)

        # Extract brands
        try:
            brand_menu = wait.until(EC.presence_of_element_located((By.XPATH, "//summary[contains(@class, 'header__menu-item') and contains(., 'Shop by Brand')]")))
            driver.execute_script("arguments[0].click();", brand_menu)

            brands_container = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'wbmenufull')]")))
            brands = brands_container.find_elements(By.XPATH, ".//div[contains(@class, 'wbmenuinner')]/a")

            brand_names = [brand.text.strip() for brand in brands if brand.text.strip()]

            # Add brand data to the list
            data.append({
                "Main Category": "Brands",
                "Subcategory": "N/A",
                "Items": ", ".join(brand_names)
            })
            print("Brand data extracted successfully!")

        except Exception as e:
            print(f"Error extracting brand data: {e}")
            print(traceback.format_exc())

        # Extract categories
        try:
            all_categories_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@class='mega-menu-title']")))
            driver.execute_script("arguments[0].click();", all_categories_btn)
            time.sleep(2)

            # Find all main categories
            main_categories = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[contains(@tabindex, '0')]")))

            if not main_categories:
                print("No main categories found!")
                return

            print(f"Found {len(main_categories)} main categories")

            for category in main_categories:
                try:
                    category_name = category.text.strip()
                    print(f"Processing category: {category_name}")

                    driver.execute_script("arguments[0].scrollIntoView(true);", category)
                    category.click()
                    time.sleep(2)

                    # Extract subcategories
                    subcategories = category.find_elements(By.XPATH, ".//div[contains(@class, 'wbmenuinner')]/a[contains(@href, 'collections')]")

                    if subcategories:
                        for subcategory in subcategories:
                            subcategory_name = subcategory.text.strip()
                            subcategory_url = subcategory.get_attribute("href")

                            # Extract items under this subcategory
                            subcategory_container = subcategory.find_element(By.XPATH, "./ancestor::div[contains(@class, 'wbmenuinner')]")
                            items = subcategory_container.find_elements(By.XPATH, ".//ul[contains(@class, 'header__submenu')]//li//a")
                            item_names = [item.text.strip() for item in items if item.text.strip()]
                            items_str = ", ".join(item_names) if item_names else "N/A"

                            # Append subcategory data
                            data.append({
                                'Main Category': category_name,
                                'Subcategory': subcategory_name,
                                'Items': items_str
                            })
                    else:
                        print(f"No subcategories found for {category_name}")

                except Exception as e:
                    print(f"Error processing category {category_name}: {e}")
                    print(traceback.format_exc())

        except Exception as e:
            print(f"Error extracting categories: {e}")
            print(traceback.format_exc())

        # Save data
        if data:
            os.makedirs(folder_name, exist_ok=True)
            df = pd.DataFrame(data)
            df.to_csv(os.path.join(folder_name, "navbar.csv"), index=False)
            print(f"Data saved to: {os.path.join(folder_name, 'navbar.csv')}")
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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Find all category sections with sliders
    category_sections = driver.find_elements(By.XPATH, "//slider-component[contains(@class, 'slider-component-desktop')]")

    for section in category_sections:
        try:
            # Extract main category name
            try:
                main_category = section.find_element(By.XPATH, ".//h2[contains(@class, 'h1')]").text.strip()
            except:
                main_category = section.find_element(By.XPATH, ".//h2").text.strip()

            print(f"\nScraping main category: {main_category}")

            # Find all products in this category
            products = section.find_elements(By.XPATH, ".//li[contains(@class, 'slider__slide')]")
            print(f"Found {len(products)} products in {main_category}")

            for product in products:
                try:
                    # Product Name
                    try:
                        name = product.find_element(By.XPATH, ".//h3[contains(@class, 'card__heading')]").text.strip()
                        if not name:
                            name = product.find_element(By.XPATH, ".//h3").text.strip()
                        name = name.replace('"', "'")
                    except:
                        name = "N/A"

                    # Product Category (brand)
                    try:
                        product_category = product.find_element(By.XPATH, ".//div[contains(@class, 'product__vendor')]").text.strip()
                    except:
                        product_category = "N/A"

                    # Prices
                    try:
                        current_price = product.find_element(By.XPATH, ".//span[contains(@class, 'price-item--sale') or contains(@class, 'card_sale_price')]").text.strip()
                    except:
                        current_price = "N/A"

                    try:
                        original_price = product.find_element(By.XPATH, ".//small[contains(@class, 'card_compare_price')]").text.strip()
                        if not original_price:
                            original_price = current_price  # If no sale, original = current
                    except:
                        original_price = current_price

                    # Add to product data
                    product_data.append({
                        'Timestamp': timestamp,
                        'Main Category': main_category,
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

        # Path for the CSV file
        csv_path = os.path.join(folder_name, "products.csv")

        # Append to the CSV file if it exists, otherwise create a new one
        if os.path.exists(csv_path):
            df.to_csv(csv_path, mode='a', header=False, index=False)  # Append mode
        else:
            df.to_csv(csv_path, mode='w', header=True, index=False)   # Write mode for new file

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
    # url = input("Enter the website URL: ").strip()
    # folder_name = input("Enter the folder name to save data: ").strip()
    url = "https://abedtahan.com/"
    folder_name = "Abed_Csv"
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