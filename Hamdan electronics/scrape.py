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

logging.basicConfig(filename="scraper.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# NLTK 
nltk.download("stopwords")
stop_words = set(stopwords.words("english"))

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
    
    title = soup.title.string if soup.title else "No title found"
    meta_desc = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc["content"] if meta_desc else "No meta description found"
    meta_keywords = soup.find("meta", attrs={"name": "keywords"})
    meta_keywords = meta_keywords["content"].split(",") if meta_keywords else []
    
    df = pd.DataFrame({"Title": [title], "Meta Description": [meta_desc], "Meta Keywords": [", ".join(meta_keywords)]})
    df.to_csv(os.path.join(folder_name, "meta_data.csv"), index=False)
    logging.info("Meta data extracted successfully")

def extract_headings_and_strong_words(url, folder_name):
    soup = fetch_html(url)
    if not soup:
        return
    
    headings = [heading.get_text(strip=True) for tag in ["h1", "h2", "h3", "h4", "h5", "h6"] for heading in soup.find_all(tag)]
    strong_words = [word.get_text(strip=True) for word in soup.find_all(["strong", "b", "em"])]
    
    max_length = max(len(headings), len(strong_words))
    headings.extend([""] * (max_length - len(headings)))
    strong_words.extend([""] * (max_length - len(strong_words)))
    
    df = pd.DataFrame({"Headings": headings, "Strong Words": strong_words})
    df.to_csv(os.path.join(folder_name, "headings_strong_words.csv"), index=False)
    logging.info("Headings and strong words extracted successfully")

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
        threading.Thread(target=extract_keywords, args=(url, folder_name))
    ]
    
    for thread in threads:
        thread.start()
    
    for thread in threads:
        thread.join()
    
    print("completed. Check folder for results")