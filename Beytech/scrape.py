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
        
        contacts = []
        
        # 1. Extract phone numbers
        phone_elements = soup.select('a[href^="tel:"]')
        for phone in phone_elements:
            contacts.append({
                'Type': 'Phone',
                'Value': phone.get('href').replace('tel:', '').strip(),
                'Source': 'Phone Link'
            })
        
        # 2. Extract WhatsApp numbers
        whatsapp_elements = soup.find_all(text=lambda text: text and 'WA:' in text)
        for wa in whatsapp_elements:
            contacts.append({
                'Type': 'WhatsApp',
                'Value': str(wa).split('WA:')[-1].strip(),
                'Source': 'WA Text'
            })
        
        # 3. Extract emails
        email_elements = soup.select('a[href^="mailto:"]')
        for email in email_elements:
            contacts.append({
                'Type': 'Email',
                'Value': email.get('href').replace('mailto:', '').strip(),
                'Source': 'Email Link'
            })
        
        # 4. Extract social media links
        social_platforms = {
            'facebook.com': 'Facebook',
            'instagram.com': 'Instagram',
            'linkedin.com': 'LinkedIn',
            'youtube.com': 'YouTube'
        }
        
        for domain, platform in social_platforms.items():
            social_links = soup.select(f'a[href*="{domain}"]')
            for link in social_links:
                contacts.append({
                    'Type': 'Social Media',
                    'Value': link.get('href').strip(),
                    'Platform': platform,
                    'Source': 'Social Link'
                })
        
        # 5. Extract address information
        address_elements = soup.select('[class*="address"], [class*="location"], [id*="address"], [id*="location"]')
        for addr in address_elements:
            address_text = addr.get_text(strip=True)
            if address_text and len(address_text) > 10:  # Basic validation
                contacts.append({
                    'Type': 'Address',
                    'Value': address_text,
                    'Source': 'Address Element'
                })
        
        # 6. Extract contact forms (newsletter signups)
        contact_forms = soup.select('form[action*="contact"], form[id*="contact"], form[class*="contact"]')
        for form in contact_forms:
            form_action = form.get('action', '').strip()
            if form_action:
                contacts.append({
                    'Type': 'Contact Form',
                    'Value': urljoin(url, form_action),
                    'Source': 'Form Action'
                })
        
        # Save all contacts to a single file
        if contacts:
            os.makedirs(folder_name, exist_ok=True)
            contacts_path = os.path.join(folder_name, "contacts.csv")
            df = pd.DataFrame(contacts)
            
            # Reorder columns for better readability
            column_order = ['Type', 'Value', 'Platform', 'Source']
            df = df.reindex(columns=[col for col in column_order if col in df.columns])
            
            df.to_csv(contacts_path, index=False)
            print(f"Extracted {len(df)} contacts to {contacts_path}")
            return df
        else:
            print("No contact information found")
            return None
            
    except Exception as e:
        print(f"Error extracting contacts: {e}")
        traceback.print_exc()
        return None
    
def extract_headings_and_strong_words(url, folder_name):

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
            (By.XPATH, "//ul[contains(@class, 'mega-menu')]/li[contains(@class, 'mega-menu-item')]/a")
        ))
        
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
                    
                    # Add to data (maintaining your perfect format)
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
            
    # ------------------------------- PRODUCT EXTRACTION -----------------------------------------------
    
    # Re-initialize WebDriver for product scraping
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    time.sleep(5)  # Allow time for page load

    # Accept cookies if present
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

    # Get all section titles first
    try:
        sections = driver.find_elements(By.XPATH, "//div[contains(@class, 'section-title-container')]")
        print(f"Found {len(sections)} sections on page")
        
        # Process each section
        for section in sections:
            try:
                # Get section title
                section_title = section.find_element(By.XPATH, ".//span[contains(@class, 'section-title-main')]").text.strip()
                print(f"\nProcessing section: {section_title}")
                
                # Find the next product grid after this section
                next_sibling = section.find_element(By.XPATH, "./following-sibling::div[contains(@class, 'row') and contains(@class, 'slider')][1]")
                
                # Get products in this section
                products = next_sibling.find_elements(By.XPATH, ".//div[contains(@class, 'product-small') and contains(@class, 'box')]")
                print(f"Found {len(products)} products in this section")
                
                for product in products:
                    try:
                        # Scroll product into view
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", product)
                        time.sleep(0.3)
                        
                        # Product Name
                        try:
                            name = product.find_element(By.XPATH, ".//p[contains(@class, 'product-title')]/a").text.strip()
                            name = name.replace('"', "'")
                        except:
                            name = "N/A"
                        
                        # Skip if duplicate or no name
                        if name == "N/A" or name in seen_products:
                            continue
                        seen_products.add(name)
                        
                        # Prices
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
                        
                        
                        # Add to product data with category
                        product_data.append({
                            'Timestamp': timestamp,
                            'Category': section_title,
                            'Product Name': name,
                            'Current Price': current_price,
                            'Original Price': original_price,
                           
                        })
                        
                    except Exception as e:
                        print(f"Error processing product: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error processing section: {e}")
                continue
                
    except Exception as e:
        print(f"Error finding sections: {e}")
        traceback.print_exc()

    driver.quit()

    # Save results
    if product_data:
        os.makedirs(folder_name, exist_ok=True)
        df = pd.DataFrame(product_data)
        
        # Reorder columns
        df = df[['Timestamp', 'Category', 'Product Name', 'Current Price', 'Original Price']]
        
        df.to_csv(os.path.join(folder_name, "products.csv"), index=False)
        print(f"\nSuccessfully extracted {len(product_data)} products with categories")
        return df
    else:
        print("No products found")
        return None
    # Re-initialize WebDriver for product scraping
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    # driver.get(url)
    # time.sleep(5)  # Allow time for page load

    # # Accept cookies if present
    # try:
    #     cookie_accept = WebDriverWait(driver, 5).until(
    #         EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'AGREE')]"))
    #     )
    #     cookie_accept.click()
    #     time.sleep(1)
    # except:
    #     pass

    # product_data = []
    # seen_products = set()
    # timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # def process_products_list(section_title, products_list):
    #     """Helper function to process products in list format"""
    #     products = products_list.find_elements(By.XPATH, "./li")
    #     print(f"Found {len(products)} products in {section_title} section")
        
    #     for product in products:
    #         try:
    #             # Product Name
    #             try:
    #                 name = product.find_element(By.XPATH, ".//span[contains(@class, 'product-title')]").text.strip()
    #                 name = name.replace('"', "'")
    #             except:
    #                 name = "N/A"
                
    #             # Skip if duplicate or no name
    #             if name == "N/A" or name in seen_products:
    #                 continue
    #             seen_products.add(name)
                
    #             # Prices - handle both regular and sale prices
    #             try:
    #                 # Try to get sale price first
    #                 current_price = product.find_element(By.XPATH, ".//ins//span[contains(@class, 'amount')]").text.strip()
    #                 original_price = product.find_element(By.XPATH, ".//del//span[contains(@class, 'amount')]").text.strip()
    #             except:
    #                 try:
    #                     # If no sale price, get regular price
    #                     current_price = product.find_element(By.XPATH, ".//span[contains(@class, 'amount')]").text.strip()
    #                     original_price = current_price
    #                 except:
    #                     current_price = "N/A"
    #                     original_price = "N/A"
                
    #             # Product URL
    #             try:
    #                 product_url = product.find_element(By.XPATH, ".//a").get_attribute("href")
    #             except:
    #                 product_url = "N/A"
                
    #             # Add to product data
    #             product_data.append({
    #                 'Timestamp': timestamp,
    #                 'Category': section_title,
    #                 'Product Name': name,
    #                 'Current Price': current_price,
    #                 'Original Price': original_price,
    #                 'Product URL': product_url
    #             })
                
    #         except Exception as e:
    #             print(f"Error processing product in {section_title}: {e}")
    #             continue

    # # 1. Process regular sections (carousel format)
    # try:
    #     sections = driver.find_elements(By.XPATH, "//div[contains(@class, 'section-title-container')]")
    #     print(f"Found {len(sections)} sections on page")
        
    #     for section in sections:
    #         try:
    #             # Get section title
    #             section_title = section.find_element(By.XPATH, ".//span[contains(@class, 'section-title-main')]").text.strip()
    #             print(f"\nProcessing section: {section_title}")
                
    #             # Check if this is followed by a product list (special case)
    #             try:
    #                 products_list = section.find_element(By.XPATH, "./following::ul[contains(@class, 'ux-products-list')][1]")
    #                 process_products_list(section_title, products_list)
    #                 continue  # Skip the carousel processing for this section
    #             except:
    #                 pass
                
    #             # Regular carousel processing
    #             try:
    #                 next_sibling = section.find_element(By.XPATH, "./following-sibling::div[contains(@class, 'row') and contains(@class, 'slider')][1]")
    #                 products = next_sibling.find_elements(By.XPATH, ".//div[contains(@class, 'product-small') and contains(@class, 'box')]")
    #                 print(f"Found {len(products)} products in this section")
                    
    #                 for product in products:
    #                     try:
    #                         # Scroll product into view
    #                         driver.execute_script("arguments[0].scrollIntoView({block:'center'});", product)
    #                         time.sleep(0.3)
                            
    #                         # Product Name
    #                         try:
    #                             name = product.find_element(By.XPATH, ".//p[contains(@class, 'product-title')]/a").text.strip()
    #                             name = name.replace('"', "'")
    #                         except:
    #                             name = "N/A"
                            
    #                         # Skip if duplicate or no name
    #                         if name == "N/A" or name in seen_products:
    #                             continue
    #                         seen_products.add(name)
                            
    #                         # Prices
    #                         try:
    #                             current_price = product.find_element(By.XPATH, ".//ins//span[contains(@class, 'amount')]").text.strip()
    #                         except:
    #                             try:
    #                                 current_price = product.find_element(By.XPATH, ".//span[contains(@class, 'amount')]").text.strip()
    #                             except:
    #                                 current_price = "N/A"
                            
    #                         try:
    #                             original_price = product.find_element(By.XPATH, ".//del//span[contains(@class, 'amount')]").text.strip()
    #                         except:
    #                             original_price = current_price
                            
                            
    #                         # Add to product data with category
    #                         product_data.append({
    #                             'Timestamp': timestamp,
    #                             'Category': section_title,
    #                             'Product Name': name,
    #                             'Current Price': current_price,
    #                             'Original Price': original_price,
    #                         })
                            
    #                     except Exception as e:
    #                         print(f"Error processing product: {e}")
    #                         continue
                            
    #             except Exception as e:
    #                 print(f"Error processing carousel products: {e}")
    #                 continue
                    
    #         except Exception as e:
    #             print(f"Error processing section: {e}")
    #             continue
                
    # except Exception as e:
    #     print(f"Error finding sections: {e}")
    #     traceback.print_exc()

    # # 2. Process special widget sections (Latest, Trending, On Sale)
    # try:
    #     widget_blocks = driver.find_elements(By.XPATH, "//div[contains(@id, 'block-') and contains(@class, 'widget_block')]")
    #     for widget in widget_blocks:
    #         try:
    #             # Get section title
    #             section_title = widget.find_element(By.XPATH, ".//span[contains(@class, 'section-title-main')]").text.strip()
    #             print(f"\nProcessing widget section: {section_title}")
                
    #             # Find the products list
    #             products_list = widget.find_element(By.XPATH, ".//ul[contains(@class, 'ux-products-list')]")
    #             process_products_list(section_title, products_list)
                
    #         except Exception as e:
    #             print(f"Error processing widget section: {e}")
    #             continue
                
    # except Exception as e:
    #     print(f"Error finding widget sections: {e}")
    #     traceback.print_exc()

    # driver.quit()

    # # Save results
    # if product_data:
    #     os.makedirs(folder_name, exist_ok=True)
    #     df = pd.DataFrame(product_data)
        
    #     # Reorder columns
    #     df = df[['Timestamp', 'Category', 'Product Name', 'Current Price', 'Original Price']]
        
    #     df.to_csv(os.path.join(folder_name, "products_with_categories.csv"), index=False)
    #     print(f"\nSuccessfully extracted {len(product_data)} products with categories")
    #     return df
    # else:
    #     print("No products found")
    #     return None
    
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