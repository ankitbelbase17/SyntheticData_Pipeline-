import requests

url = "https://www.amazon.com/Runaway-Label-Womens-Sondrey-Casanova/dp/B0DQWJYG1D/?th=1&psc=1"
api_key = "CRAWLBASE_API_KEY"  # Replace with your actual Crawlbase API key

params = {
    "token": api_key,
    "url": url,
    "smart": "true"
}

response = requests.get("https://api.crawlbase.com/", params=params)
print(response.text)