import os
import pandas as pd

def clean_hamdan():
    try:
        folder_csv_path = "../Hamdan_Csv"
        csv_file_path = os.path.join(folder_csv_path, "products.csv")
        cleaned_csv_path = os.path.join(folder_csv_path, "cleaned_Csv.csv")

        if not os.path.exists(csv_file_path):
            print(f"Error: {csv_file_path} not found.")
            return

        df = pd.read_csv(csv_file_path)

        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df.dropna(how="all", inplace=True)

        expected_columns = ["Timestamp", "Main Category", "Product Name", "Current Price", "Original Price"]
        df = df[[col for col in expected_columns if col in df.columns]]

        def clean_price(val):
            if isinstance(val, str):
                val = val.replace("USD", "").replace("$", "").replace(",", "").strip()
            return float(val)

        df["Current Price"] = df["Current Price"].apply(clean_price)
        df["Original Price"] = df["Original Price"].apply(clean_price)

        # If cleaned CSV exists, append new data
        if os.path.exists(cleaned_csv_path):
            existing_df = pd.read_csv(cleaned_csv_path)
            combined_df = pd.concat([existing_df, df], ignore_index=True)

            # drop duplicates based on all columns
            combined_df.drop_duplicates(inplace=True)

            combined_df.to_csv(cleaned_csv_path, index=False)
        else:
            # If not exists, just save new data
            df.to_csv(cleaned_csv_path, index=False)

        print(f"Hamdan_Csv cleaned and updated. Saved to {cleaned_csv_path}.")
    except Exception as e:
        print(f"Error cleaning Hamdan_Csv: {e}")

if __name__ == "__main__":
    clean_hamdan()
