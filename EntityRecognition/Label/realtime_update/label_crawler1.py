"""
@https://github.com/DeveloperJon/wordCloudScraperEtherscan/blob/main/main.py
Version: 0.0.0.1
Developer: Spag.sol AKA Spaghetti Code
Date: 2024-10-26
"""

import time
import random
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

BASE_URL = "https://etherscan.io"
output_file = "scraped_data.json"

# Load existing data from the file or initialize an empty data set
def load_existing_data():
    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
        try:
            with open(output_file, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError:
            print(f"Warning: {output_file} contains invalid JSON. Starting with an empty data set.")
            return []
    else:
        return []

all_data = load_existing_data()

# Categorize URLs based on their path
def categorize_url(url):
    if "accounts" in url:
        return "accounts"
    elif "tokens" in url:
        return "tokens"
    else:
        return "other"

# Setup Chrome browser using Selenium in headless mode
def setup_browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")  # Required for headless mode
    options.add_argument("--ignore-certificate-errors")  # Bypass SSL certificate errors

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

# Extract URLs and scrape data by loading the page with Selenium
def extract_urls_and_scrape(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    for a_tag in soup.find_all('a', href=True):
        url_path = a_tag['href']
        
        if not url_path.startswith("/"):
            continue
        
        category = categorize_url(url_path)
        name = url_path.split('/')[-1]
        formatted_url = f"/{category}/{name}"
        full_url = BASE_URL + formatted_url
        print(f"Found {category} URL: {full_url}")
        
        existing_entry = next((entry for entry in all_data if entry['url'] == formatted_url), None)
        table_data = scrape_table_data(full_url)
        
        new_entry = {
            'url': formatted_url,
            'category': category,
            'name': name,
            'table_data': table_data
        }

        if existing_entry:
            print(f"Updating existing entry for {formatted_url}")
            all_data[all_data.index(existing_entry)] = new_entry
        else:
            print(f"Adding new entry for {formatted_url}")
            all_data.append(new_entry)
        
        save_to_file(all_data)
        time.sleep(random.uniform(5, 15))

# Scrape table data using Selenium and BeautifulSoup
# Don't use sleep - TERRIBLE WAY OF DOING THIS/PLACEHOLDER
def scrape_table_data(url):
    driver = setup_browser()
    try:
        print(f"Accessing {url} via browser")
        driver.get(url)
        time.sleep(3)  # Change this, this is just a placeholder

        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        table = soup.find('table')

        if not table:
            print(f"No table found at {url}")
            return None

        headers = [header.text.strip() for header in table.find_all('th')]

        rows_data = []
        for row in table.find_all('tr')[1:]:
            cells = [cell.text.strip() for cell in row.find_all('td')]
            if cells:
                rows_data.append(cells)

        return {
            "headers": headers,
            "rows": rows_data
        }

    except Exception as e:
        print(f"Failed to retrieve data from {url}: {str(e)}")
        return None

    finally:
        driver.quit()

# Save the scraped data to the output JSON file
def save_to_file(data):
    try:
        with open(output_file, 'w') as file:
            json.dump(data, file, indent=4)
        print(f"Data saved to {output_file}")
    except Exception as e:
        print(f"Error saving data: {str(e)}")

# Read the HTML input from the rawhtml.html file
def read_html_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"File {file_path} not found")
        return None

# Execute the scraping process if HTML input is available
html_input = read_html_from_file('rawhtml.html')
if html_input:
    extract_urls_and_scrape(html_input)