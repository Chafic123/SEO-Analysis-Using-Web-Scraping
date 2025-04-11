import os
import subprocess

def run_scrapers(base_path="."):
    for root, dirs, files in os.walk(base_path):
        print(f"Checking directory: {root}")

        if 'scrape.py' in files:
            scrape_path = os.path.join(root, 'scrape.py')
            print(f"Found and running: {scrape_path}")
            try:
                result = subprocess.run(["python", scrape_path], check=True, capture_output=True, text=True)
                print(f"Success: {scrape_path}\n{result.stdout}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to run scrape.py:\n{e.stderr}")
                continue  

            clean_path = os.path.join(root, 'clean.py')
            if 'clean.py' in files:
                print(f"Running clean script: {clean_path}")
                try:
                    clean_result = subprocess.run(["python", clean_path], check=True, capture_output=True, text=True)
                    print(f"Success: {clean_path}\n{clean_result.stdout}")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to run clean.py:\n{e.stderr}")
            else:
                print(f"clean.py not found in {root}")

if __name__ == "__main__":
    run_scrapers()
