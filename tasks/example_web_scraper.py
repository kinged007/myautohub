"""
---
title: "Web Scraper Task"
description: "Scrapes a website and saves data every 30 minutes"
dependencies:
  - "requests>=2.25.0"
  - "beautifulsoup4>=4.9.3"
enabled: true
timeout: 300
retry_count: 2
retry_delay: 60
---
"""

from task_scheduler.decorators import repeat, every
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path

@repeat(every(30).minutes)
def start():
    """Scrape website data every 30 minutes"""
    try:
        print("Starting web scraping task...")
        
        # Make request to example website
        url = "https://httpbin.org/json"
        headers = {
            'User-Agent': 'Task-Scheduler/1.0'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        # Add timestamp
        data['scraped_at'] = datetime.now().isoformat()
        data['url'] = url
        
        # Save to file
        data_dir = Path("data/examples")
        data_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = data_dir / f"scraped_data_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Successfully scraped data and saved to {filename}")
        print(f"Data keys: {list(data.keys())}")
        
    except requests.RequestException as e:
        print(f"Request error: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
