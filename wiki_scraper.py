from bs4 import BeautifulSoup
import requests


def scrape(entity_name):
    url = f'https://en.wikipedia.org/wiki/{entity_name}'
    response = requests.get(url)
    
    if response.status_code != 200:
        return None
    
    soup = BeautifulSoup(response.content, 'html.parser')
    links = []
    
    # Extract all the hyperlinks from the page
    for link in soup.find_all('a', href=True):
        href = link['href']
        # Filtering the articles that are not on wikipedia
        if href.startswith('/wiki/') and ':' not in href:
            links.append(href.split('/wiki/')[1])
    
    return links