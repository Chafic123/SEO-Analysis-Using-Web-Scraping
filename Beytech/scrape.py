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
from urllib.parse import urljoin, urlparse
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
        print('Access')
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
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        
        # Wait for page to load
        time.sleep(3)
        
        # Extract ALL links with href attribute
        all_links = []
        elements = driver.find_elements(By.XPATH, "//div[@id='top-bar']//a[@href]")
        
        for element in elements:
            href = element.get_attribute('href')
            text = element.text.strip() if element.text.strip() else "N/A"
            data_label = element.get_attribute('data-label') or "N/A"
            
            all_links.append({
                'URL': href,
                'Anchor Text': text,
                'Type': data_label
            })
        
        # Save to CSV
        if all_links:
            os.makedirs(folder_name, exist_ok=True)
            df = pd.DataFrame(all_links)
            output_path = os.path.join(folder_name, "backlinks.csv")
            df.to_csv(output_path, index=False)
            print(f"Saved {len(all_links)} links to {output_path}")
            return df
        else:
            print("No links found on the page")
            return None
            
    except Exception as e:
        print(f"Error extracting links: {e}")
        return None
    finally:
        driver.quit()
    
def extract_headings_and_strong_words(url, folder_name):
    
    navbar_df = extract_navbar_data(url, folder_name)
    
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--headless")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    time.sleep(5)

    # Accept cookies
    try:
        cookie_accept = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'AGREE')]"))
        )
        cookie_accept.click()
        time.sleep(1)
    except:
        pass

    product_data = []
    seen_products = set()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def parse_product(product, section_title, product_type="carousel"):
        try:
            if product_type == "carousel":
                name = product.find_element(By.XPATH, ".//p[contains(@class, 'product-title')]/a | .//span[contains(@class, 'product-title')]").text.strip()
            else:  # list type
                name = product.find_element(By.XPATH, ".//span[contains(@class, 'product-title')]").text.strip()
            name = name.replace('"', "'")
        except:
            name = "N/A"
        
        if name == "N/A" or name in seen_products:
            return None
        seen_products.add(name)

        # Price extraction
        try:
            current_price = product.find_element(By.XPATH, ".//ins//span[contains(@class, 'amount')]").text.strip()
        except:
            try:
                current_price = product.find_element(By.XPATH, ".//span[contains(@class, 'amount')]").text.strip()
            except:
                current_price = "N/A"

        try:
            original_price = product.find_element(By.XPATH, ".//del//span[contains(@class, 'amount')]").text.strip()
        except:
            original_price = current_price

        return {
            'Timestamp': timestamp,
            'Main Category': section_title if section_title.strip() else "LATEST", 
            'Product Name': name,
            'Current Price': current_price,
            'Original Price': original_price,
        }

    def process_carousel(section_title, container):
        products = container.find_elements(By.XPATH, ".//div[contains(@class, 'product-small') and contains(@class, 'box')]")
        print(f"Found {len(products)} carousel products in {section_title}")
        for product in products:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", product)
                time.sleep(0.3)
            except:
                pass
            result = parse_product(product, section_title, "carousel")
            if result:
                product_data.append(result)

    def process_list(section_title, ul_element):
        products = ul_element.find_elements(By.XPATH, "./li")
        print(f"Found {len(products)} list products in {section_title}")
        for product in products:
            result = parse_product(product, section_title, "list")
            if result:
                product_data.append(result)

    # Process all sections (both carousels and lists)
    try:
        sections = driver.find_elements(By.XPATH, "//div[contains(@class, 'section-title-container')]")
        print(f"Found {len(sections)} sections")

        for section in sections:
            try:
                section_title = section.find_element(By.XPATH, ".//span[contains(@class, 'section-title-main')]").text.strip()
                print(f"\nProcessing section: {section_title}")
                
                # First try to find a carousel
                try:
                    carousel = section.find_element(By.XPATH, "./following-sibling::div[contains(@class, 'row') and contains(@class, 'slider')][1]")
                    process_carousel(section_title, carousel)
                except:
                    # If no carousel, try to find a product list
                    try:
                        ul = section.find_element(By.XPATH, "./following::ul[contains(@class, 'product_list_widget') or contains(@class, 'ux-products-list')][1]")
                        process_list(section_title, ul)
                    except:
                        print(f"No recognizable product format in section: {section_title}")
            except Exception as e:
                print(f"Error processing section: {e}")
    except Exception as e:
        print("Error finding sections")
        traceback.print_exc()

    # Process special widgets - Skip if we've already processed them as sections
    try:
        widgets = driver.find_elements(By.XPATH, "//div[contains(@id, 'block-') and contains(@class, 'widget_block') and not(contains(@class, 'section-title-container'))]")
        for widget in widgets:
            try:
                section_title = widget.find_element(By.XPATH, ".//span[contains(@class, 'section-title-main')]").text.strip()
                print(f"\nProcessing widget: {section_title}")
                ul = widget.find_element(By.XPATH, ".//ul[contains(@class, 'product_list_widget') or contains(@class, 'ux-products-list')]")
                process_list(section_title, ul)
            except Exception as e:
                print(f"Error processing widget: {e}")
    except Exception as e:
        print("Error finding widgets")
        traceback.print_exc()

    driver.quit()

    # Save results
if product_data:
    os.makedirs(folder_name, exist_ok=True)
    df = pd.DataFrame(product_data)
    
    # Clean and organize columns
    columns_order = [
        'Timestamp', 'Main Category', 'Product Name', 
        'Current Price', 'Original Price']
    df = df[columns_order]
    
    # Path for the CSV file
    csv_path = os.path.join(folder_name, "products.csv")
    
    # Append to the CSV file if it exists, otherwise create a new one
    if os.path.exists(csv_path):
        df.to_csv(csv_path, mode='a', header=False, index=False)  # Append mode
    else:
        df.to_csv(csv_path, mode='w', header=True, index=False)   # Write mode for new file
    
    print(f"\nSuccessfully extracted {len(df)} products. Saved to {csv_path}")
    return df
else:
    print("No products found.")
    return None


def extract_navbar_data(url, folder_name):

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--headless")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    data = []

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 5)
        
        # Step 1: Get all main categories
        main_categories = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//ul[contains(@class, 'mega-menu')]/li[contains(@class, 'mega-menu-item')]/a")))
        
        for category in main_categories:
            main_category = category.text.strip()
            if not main_category:
                continue
            
            ActionChains(driver).move_to_element(category).perform()
            time.sleep(0.5)
            
            parent_li = category.find_element(By.XPATH, "./ancestor::li")
            has_children = "mega-menu-item-has-children" in parent_li.get_attribute("class")
            
            # If no children exist, add main category with N/A values
            if not has_children:
                data.append({
                    'Main Category': main_category,
                    'Subcategory': "N/A", 
                    'Items': "N/A"
                })
                continue
                
            # Step 2: Process subcategories
            subcategories = parent_li.find_elements(By.XPATH, 
                ".//ul[contains(@class, 'mega-sub-menu')]//li[contains(@class, 'mega-menu-item') and contains(@class, 'mega-menu-item-has-children')]")
            
            # If no subcategories found but parent has children class
            if not subcategories:
                data.append({
                    'Main Category': main_category,
                    'Subcategory': "N/A",
                    'Items': "N/A"
                })
                continue
                
            for subcategory in subcategories:
                try:
                    # Get subcategory title
                    subcategory_link = subcategory.find_element(By.XPATH, ".//a[contains(@class, 'mega-menu-link')]")
                    subcategory_title = subcategory_link.text.strip()
                    
                    if not subcategory_title:
                        continue
                    
                    # Initialize items list
                    items = []
                    
                    # Step 3: Get items if they exist
                    if "mega-menu-item-has-children" in subcategory.get_attribute("class"):
                        item_elements = subcategory.find_elements(By.XPATH, 
                            ".//ul[contains(@class, 'mega-sub-menu')]/li/a")
                        items = [item.text.strip() for item in item_elements if item.text.strip()]
                    
                    # Add to data

                    data.append({
                        'Main Category': main_category,
                        'Subcategory': subcategory_title,
                        'Items': ", ".join(items) if items else "N/A"
                    })
                    
                except Exception as e:
                    print(f"Error processing subcategory: {e}")
                    continue
        
        # Save data to CSV
        if data:
            df = pd.DataFrame(data)
            os.makedirs(folder_name, exist_ok=True)
            output_path = os.path.join(folder_name, "navbar.csv")
            df.to_csv(output_path, index=False)
            print(f"Navbar data saved to: {output_path}")
        else:
            print("No data collected")
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        traceback.print_exc()
    finally:
        driver.quit()

 
def extract_keywords(url, folder_name):
    soup = fetch_html(url)
    if not soup:
        return
    
    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()
    
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
    url = "https://beytech.com.lb/"
    # folder_name = input("Enter the folder name to save data: ").strip()
    folder_name = "Beytech_Csv"
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