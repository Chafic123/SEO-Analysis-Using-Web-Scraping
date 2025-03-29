import requests
from bs4 import BeautifulSoup
from collections import Counter
import re
import pandas as pd
import os
import threading
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
import nltk
from nltk.corpus import stopwords
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

logging.basicConfig(filename="scraper.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# NLTK 
nltk.download("stopwords")
# stop_words = set(stopwords.words("english"))
# Initialize stopwords from NLTK and add custom stop words for filtering out non-relevant terms.
stop_words = set(stopwords.words("english")) | {"view", "add", "cart", "quick", "load", "price", "original"}

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
def extract_headings_and_strong_words(url, folder_name):
    
    soup = fetch_html(url)
    if not soup:
        return
    
    # Find the main navigation bar
    navbar = soup.find('ul', class_='header-nav-main')
    if not navbar:
        print("Navigation bar not found")
        return
    
    data = []
    
    # Extract top-level menu items
    for top_item in navbar.find_all('li', recursive=False):
        try:
            # Get top-level category name - properly handle text and ignore icons
            top_link = top_item.find('a', class_='nav-top-link')
            if not top_link:
                continue
                
            # Get all text while ignoring the <i> tags
            top_category = ''.join(text for text in top_link.stripped_strings if not text.startswith('i'))
            top_category = top_category.strip()
            
            # Find submenu if exists
            submenu = top_item.find('ul', class_='sub-menu')
            if submenu:
                # Extract columns in the dropdown
                for column in submenu.find_all('li', class_='nav-dropdown-col'):
                    column_title = column.find('a').get_text(strip=True)
                    
                    # Extract items in this column
                    column_items = []
                    for item in column.find_all('li'):
                        # Skip if it's a menu item with children (has its own submenu)
                        if 'menu-item-has-children' in item.get('class', []):
                            continue
                        item_text = item.get_text(strip=True)
                        if item_text and item_text != column_title:
                            column_items.append(item_text)
                    
                    # Add to data
                    if column_items:
                        data.append({
                            'Main Category': top_category,
                            'Subcategory': column_title,
                            'Items': ', '.join(column_items)
                        })
            else:
                # Single item without dropdown
                data.append({
                    'Main Category': top_category,
                    'Subcategory': '',
                    'Items': ''
                })
                
        except Exception as e:
            print(f"Error processing menu item: {e}")
            continue
    
    # Create DataFrame and save to CSV
    df = pd.DataFrame(data)
    os.makedirs(folder_name, exist_ok=True)
    df.to_csv(os.path.join(folder_name, "navbar_data.csv"), index=False)
    print("Navbar data extracted successfully")


    # Set up Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # Initialize WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    driver.get(url)
    time.sleep(5)  # Allow time for the page to load

    # Accept cookies if present
    try:
        cookie_accept = driver.find_element(By.XPATH, "//div[contains(@class, 'flatsome-cookies')]//button[contains(text(), 'Accept')]")
        cookie_accept.click()
        time.sleep(1)
    except:
        pass  # Continue if no cookie banner is found

    product_data = []

    # Find main categories
    category_sections = driver.find_elements(By.XPATH, "//div[@class='row' and .//h2]")

    for section in category_sections:
        try:
            # Extract main category name
            main_category = section.find_element(By.XPATH, './/h2').text.strip()
            print(f"\nScraping main category: {main_category}")

            # Wait for subcategories to be visible
            subcategories_row = WebDriverWait(section, 10).until(
                EC.presence_of_element_located((By.XPATH, ".//following-sibling::div[contains(@class, 'row')]"))
            )

            # Get subcategories
            subcategories = subcategories_row.find_elements(By.XPATH, ".//li[contains(@class, 'tab')]")
            
            if subcategories:
                print(f"Subcategories found: {[sub.text for sub in subcategories]}")
            else:
                print(f"No subcategories found for {main_category}")
            
            # Process each subcategory
            for subcategory in subcategories:
                subcategory_name = subcategory.text.strip()
                print(f"Processing subcategory: {subcategory_name}")

                driver.execute_script("arguments[0].click();", subcategory)
                time.sleep(2)  # Wait for products to load

                # Locate and process products after subcategory click
                try:
                    # Explicitly wait for the products to be available
                    products_slider = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'row-slider')]"))
                    )
                    
                    # Attempt to locate product items under the subcategory
                    products = products_slider.find_elements(By.XPATH, ".//div[contains(@class, 'product-small')]")
                    
                    if not products:
                        print(f"No products found in {subcategory_name} - Trying a fallback XPath")
                        # Fallback to a different XPath if the main one doesn't work
                        products = products_slider.find_elements(By.XPATH, ".//div[contains(@class, 'col') and contains(@class, 'is-selected')]")

                    print(f"Found {len(products)} products in {subcategory_name}")

                    for product in products:
                        try:
                            # Extract product details
                            try:
                                name = product.find_element(By.XPATH, ".//p[contains(@class, 'product-title')]").text.strip()
                            except:
                                
                                name = "N/A"

                            try:
                                product_category = product.find_element(By.XPATH, ".//p[contains(@class, 'category')]").text.strip()
                            except:
                                product_category = subcategory_name

                            try:
                                price_wrapper = product.find_element(By.XPATH, ".//div[contains(@class, 'price-wrapper')]")
                                try:
                                    current_price = price_wrapper.find_element(By.XPATH, ".//span[contains(@class, 'price')]//bdi").text.strip()
                                except:
                                    current_price = "N/A"

                                try:
                                    original_price = price_wrapper.find_element(By.XPATH, ".//del//bdi").text.strip()
                                except:
                                    original_price = current_price
                            except:
                                current_price = "N/A"
                                original_price = "N/A"

                            # Add product data to list
                            product_data.append({
                                'Main Category': main_category,
                                'Subcategory': subcategory_name,
                                'Product Category': product_category,
                                'Product Name': name,
                                'Current Price': current_price,
                                'Original Price': original_price,
                            })

                        except Exception as e:
                            print(f"Error processing product: {e}")
                            continue

                except Exception as e:
                    print(f"Error finding products for subcategory {subcategory_name}: {e}")
                    continue

        except Exception as e:
            print(f"Error processing category {main_category}: {e}")
            continue

    # Close driver
    driver.quit()

    # Save results
    if product_data:
        df = pd.DataFrame(product_data)
        os.makedirs(folder_name, exist_ok=True)
        df.to_csv(os.path.join(folder_name, "products.csv"), index=False)
        print(f"\nSuccessfully extracted {len(product_data)} products")
    else:
        print("No products found")


    

def extract_keywords(url, folder_name):
    soup = fetch_html(url)
    if not soup:
        return
    
    page_text = soup.get_text()
    
    # Step 1: Extracting SEO keywords (simple word frequency count after filtering stop words)
    words = re.findall(r"\b[a-zA-Z]{3,}\b", page_text.lower())
    filtered_words = [word for word in words if word not in stop_words]
    
    # Count the frequency of each word
    common_keywords = Counter(filtered_words).most_common(20)
    
    # Step 2: Extracting TF-IDF keywords (terms weighted by their importance in the document)
    vectorizer = TfidfVectorizer(stop_words="english", max_features=50, ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform([" ".join(filtered_words)])
    tfidf_keywords = vectorizer.get_feature_names_out()

    # Step 3: Saving the results into CSV files
    df_common = pd.DataFrame(common_keywords, columns=["Keyword", "Count"])
    df_common.to_csv(os.path.join(folder_name, "seo_keywords.csv"), index=False)
    
    df_tfidf = pd.DataFrame(tfidf_keywords, columns=["TF-IDF Keywords"])
    df_tfidf.to_csv(os.path.join(folder_name, "tfidf_keywords.csv"), index=False)
    
    logging.info("Keywords extracted and saved successfully.")

if __name__ == "__main__":
    url = input("Enter the website URL: ").strip()
    folder_name = input("Enter the folder name to save data: ").strip()
    os.makedirs(folder_name, exist_ok=True)
    
    threads = [
        threading.Thread(target=extract_meta_data, args=(url, folder_name)),
        threading.Thread(target=extract_headings_and_strong_words, args=(url, folder_name)),
        threading.Thread(target=extract_keywords, args=(url, folder_name))
    ]
    
    for thread in threads:
        thread.start()
    
    for thread in threads:
        thread.join()
    
    print("completed. Check folder for results")