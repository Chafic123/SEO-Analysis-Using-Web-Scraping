import os
import pandas as pd

def clean_beytech():
    try:
        folder_csv_path = "../Beytech_Csv"
        csv_file_path = os.path.join(folder_csv_path, "products.csv")
        cleaned_csv_path = os.path.join(folder_csv_path, "cleaned_Csv.csv")

        if not os.path.exists(csv_file_path):
            print(f"Error: {csv_file_path} not found.")
            return

        df = pd.read_csv(csv_file_path)

        # Strip whitespace 
        df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)

        # Drop fully empty rows
        df.dropna(how="all", inplace=True)

        expected_columns = ["Timestamp", "Main Category", "Product Name", "Current Price", "Original Price"]
        df = df[[col for col in expected_columns if col in df.columns]]

        # Clean price columns: remove $, commas, and "USD", then convert to float
        def clean_price(val):
            if isinstance(val, str):
                val = val.replace("USD", "").replace("$", "").replace(",", "").strip()
            return float(val)

        df["Current Price"] = df["Current Price"].apply(clean_price)
        df["Original Price"] = df["Original Price"].apply(clean_price)

        if os.path.exists(cleaned_csv_path):
            existing_df = pd.read_csv(cleaned_csv_path)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.drop_duplicates(inplace=True)
            combined_df.to_csv(cleaned_csv_path, index=False)
        else:
            df.to_csv(cleaned_csv_path, index=False)

        print(f"Beytech_Csv cleaned and updated. Saved to {cleaned_csv_path}.")
    except Exception as e:
        print(f"Error cleaning Beytech_Csv: {e}")

def clean_backlinks():
    try:
        folder_csv_path = "../Beytech_Csv"
        csv_file_path = os.path.join(folder_csv_path, "backlinks.csv")
        cleaned_csv_path = os.path.join(folder_csv_path, "backlinks.csv")

        if not os.path.exists(csv_file_path):
            print(f"Error: {csv_file_path} not found.")
            return

        df = pd.read_csv(csv_file_path)
        df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)
        def get_platform(row):
            if pd.notna(row["Type"]) and row["Type"] != "N/A":
                return row["Type"]
            elif pd.notna(row["Anchor Text"]) and row["Anchor Text"] != "N/A":
                return row["Anchor Text"]
            return None  # Return None for unknowns

        df["Platform"] = df.apply(get_platform, axis=1)

        # Drop rows with unknown platforms
        df.dropna(subset=["Platform"], inplace=True)

        # Select only Platform and URL columns
        cleaned_df = df[["Platform", "URL"]]

        # Optional: remove duplicates
        cleaned_df.drop_duplicates(inplace=True)

        # Save cleaned file
        cleaned_df.to_csv(cleaned_csv_path, index=False)
        print(f"Backlinks cleaned and saved to {cleaned_csv_path}.")
    except Exception as e:
        print(f"Error cleaning backlinks.csv: {e}")


if __name__ == "__main__":
    clean_backlinks()
    clean_beytech()
