import os
import pandas as pd

def clean_abed_tahhan():
    try:
        folder_csv_path = "../Abed_Csv"  
        csv_file_path = os.path.join(folder_csv_path, "products.csv")

        if not os.path.exists(csv_file_path):
            print(f"Error: {csv_file_path} not found.")
            return

        df = pd.read_csv(csv_file_path)

        # Strip whitespace 
        df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)

        # Drop rows that are completely empty
        df.dropna(how="all", inplace=True)

        expected_columns = [
            "Timestamp", "Main Category", "Product Category",
            "Product Name", "Current Price", "Original Price"
        ]
        df = df[[col for col in expected_columns if col in df.columns]]

        def clean_price(val):
            if isinstance(val, str):
                val = val.replace("USD", "").replace("$", "").replace(",", "").strip()
            return float(val)

        if "Current Price" in df.columns:
            df["Current Price"] = df["Current Price"].apply(clean_price)
        if "Original Price" in df.columns:
            df["Original Price"] = df["Original Price"].apply(clean_price)

        cleaned_csv_path = os.path.join(folder_csv_path, "cleaned_Csv.csv")
        if os.path.exists(cleaned_csv_path):
            df.to_csv(cleaned_csv_path, mode='a', header=False, index=False)
        else:
            df.to_csv(cleaned_csv_path, index=False)

        print(f"Abed_Csv cleaned and updated. Saved to {cleaned_csv_path}.")
    except Exception as e:
        print(f"Error cleaning Abed_Csv: {e}")

if __name__ == "__main__":
    clean_abed_tahhan()
