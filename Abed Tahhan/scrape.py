import requests
from bs4 import BeautifulSoup
from collections import Counter
import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

url = "https://abedtahan.com/"

headers = {"User-Agent": "Mozilla/5.0"}

response = requests.get(url, headers=headers)

soup = BeautifulSoup(response.text, "html.parser")

title = soup.title.string if soup.title else "No title found"

meta_desc = soup.find("meta", attrs={"name": "description"})
meta_desc = meta_desc["content"] if meta_desc else "No meta description found"

meta_keywords = soup.find("meta", attrs={"name": "keywords"})
meta_keywords = meta_keywords["content"].split(",") if meta_keywords else []

headings = []
for tag in ["h1", "h2", "h3"]:
    for heading in soup.find_all(tag):
        headings.append(heading.get_text(strip=True))

strong_words = [word.get_text(strip=True) for word in soup.find_all(["strong", "b", "em"])]

page_text = soup.get_text()
words = re.findall(r"\b[a-zA-Z]{4,}\b", page_text.lower())  

stopwords = {"sold", "cart", "default", "title", "account", "list", "home", "sale", "shop", "order"}
filtered_words = [word for word in words if word not in stopwords]

common_keywords = Counter(filtered_words).most_common(20)  # Top 20 keywords

vectorizer = TfidfVectorizer(stop_words="english", max_features=20)
tfidf_matrix = vectorizer.fit_transform([" ".join(filtered_words)])
tfidf_keywords = vectorizer.get_feature_names_out()

df = pd.DataFrame(common_keywords, columns=["Keyword", "Count"])
df.to_csv("seo_keywords.csv", index=False)

print(f"Title: {title}")
print(f"Meta Description: {meta_desc}")
print(f"Meta Keywords: {meta_keywords}")
print(f"Headings (H1, H2, H3): {headings[:10]}") 
print(f"Strong/Bold/Emphasized Words: {strong_words}")
print(f"Most Common Keywords: {common_keywords}")
print(f"Top TF-IDF Keywords: {tfidf_keywords}")




