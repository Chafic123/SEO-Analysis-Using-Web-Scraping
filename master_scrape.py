import os
import subprocess

def run_scrapers(base_path="."):
    print("🔍 Searching for scrape.py files...\n")
    
    for root, dirs, files in os.walk(base_path):
        if 'scrape.py' in files:
            scrape_path = os.path.join(root, 'scrape.py')
            print(f"Running: {scrape_path}")
            try:
                result = subprocess.run(["python", scrape_path], check=True, capture_output=True, text=True)
                print(f"Success: {scrape_path}\n{result.stdout}")
            except subprocess.CalledProcessError as e:
                print(f"Failed: {scrape_path}\n{e.stderr}")

if __name__ == "__main__":
    run_scrapers()
