import os
import subprocess

def run_scrapers(base_path=".", target_folders=None):
    if target_folders is None:
        target_folders = ['Abed Tahhan', 'Beytech', 'Hamdan electronics']  

    print("Searching for scrape.py files...\n")
    
    for root, dirs, files in os.walk(base_path):
        folder_name = os.path.basename(root)
        if folder_name in target_folders:
            print(f"Checking directory: {root}")
            if 'scrape.py' in files:
                scrape_path = os.path.join(root, 'scrape.py')
                print(f"Found: {scrape_path}")
                try:
                    result = subprocess.run(["python", scrape_path], check=True, capture_output=True, text=True)
                    print(f"Success: {scrape_path}\n{result.stdout}")
                except subprocess.CalledProcessError as e:
                    print(f"Failed: {scrape_path}\nError: {e.stderr}")

if __name__ == "__main__":
    run_scrapers()
