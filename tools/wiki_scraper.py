import requests
from bs4 import BeautifulSoup
import json
import re
import argparse
from typing import List, Optional, Dict
import sys
import os

# Add project root to path so we can import core.models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.models import (
    NovelNamespace, PowerHierarchy, CultivationRank, 
    Character, Novel
)

class FandomScraper:
    def __init__(self, base_url: str, novel_id: str, title: str):
        self.base_url = base_url.rstrip("/")
        self.novel_id = novel_id
        self.title = title
        self.headers = {'User-Agent': 'InfiniteLibrary/1.0'}

    def _get_soup(self, endpoint: str) -> Optional[BeautifulSoup]:
        url = f"{self.base_url}/wiki/{endpoint}"
        print(f"📡 Scraping: {url}...")
        try:
            resp = requests.get(url, headers=self.headers)
            if resp.status_code != 200:
                print(f"⚠️ Failed to fetch {url} (Status: {resp.status_code})")
                return None
            return BeautifulSoup(resp.content, 'html.parser')
        except Exception as e:
            print(f"❌ Error fetching {url}: {e}")
            return None

    def scrape_power_hierarchy(self, cultivation_page: str = "Cultivation") -> Optional[PowerHierarchy]:
        """
        Attempts to scrape cultivation ranks from a Wiki table.
        Heuristic: Looks for tables with 'Rank', 'Stage', or 'Level' headers.
        """
        soup = self._get_soup(cultivation_page)
        if not soup:
            return None

        ranks = []
        rank_counter = 1

        # Strategy 1: Look for Tables
        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text().strip().lower() for th in table.find_all("th")]
            
            # Check if this table looks like a rank list
            if any(x in headers for x in ["rank", "realm", "stage", "level"]):
                rows = table.find_all("tr")
                for row in rows:
                    cols = row.find_all(["td", "th"])
                    if not cols: continue
                    
                    # Extract text from first valid column (usually the Name)
                    # This is a heuristic; might need tuning for specific wikis
                    rank_name = cols[0].get_text().strip()
                    if not rank_name or rank_name.lower() in headers: 
                        continue
                    
                    # Clean the name (remove footnotes [1])
                    rank_name = re.sub(r'\[.*?\]', '', rank_name)
                    
                    # Attempt to find sub-realms in other columns
                    desc = cols[1].get_text().strip() if len(cols) > 1 else ""
                    
                    ranks.append(CultivationRank(
                        name=rank_name,
                        order_index=rank_counter,
                        description=desc[:100], # Keep concise
                        major_realm="Unknown", # Requires deeper parsing or manual fix
                        sub_realm=None
                    ))
                    rank_counter += 1

        # Fallback: If no tables, try Ordered Lists (common in some wikis)
        if not ranks:
            print("⚠️ No tables found. Checking lists...")
            # Look for headers containing 'Rank' or 'Realm'
            headers = soup.find_all(["h2", "h3"], string=re.compile(r"(Rank|Realm|Stage)", re.I))
            for header in headers:
                # Find the next list
                next_elem = header.find_next(["ul", "ol"])
                if next_elem:
                    for li in next_elem.find_all("li"):
                        rank_name = li.get_text().split("\n")[0].strip() # Get first line
                        rank_name = re.sub(r'\[.*?\]', '', rank_name)
                        ranks.append(CultivationRank(
                            name=rank_name,
                            order_index=rank_counter,
                            major_realm=header.get_text().strip(),
                            description=""
                        ))
                        rank_counter += 1

        if not ranks:
            print("❌ Could not extract cultivation ranks. You may need to edit 'namespace.json' manually.")
            return None

        print(f"✅ Extracted {len(ranks)} Cultivation Ranks.")
        return PowerHierarchy(
            novel_id=self.novel_id,
            system_name="Wiki Scraped System",
            ranks=ranks
        )

    def scrape_character(self, char_name: str) -> Character:
        """
        Scrapes the Main Character's profile (Infobox + Personality).
        """
        # Wiki URLs usually use underscores for spaces
        endpoint = char_name.replace(" ", "_")
        soup = self._get_soup(endpoint)
        
        if not soup:
            raise ValueError(f"Could not find character page: {char_name}")

        # 1. Scrape Aliases from Infobox
        aliases = []
        infobox = soup.find("aside", class_="portable-infobox")
        if infobox:
            # Fandom Infoboxes often have data-source="aliases"
            alias_div = infobox.find("div", attrs={"data-source": "aliases"})
            if not alias_div:
                # Try searching text 'Aliases'
                alias_label = infobox.find(string=re.compile("Alias", re.I))
                if alias_label:
                    alias_div = alias_label.find_parent("div")
            
            if alias_div:
                # Extract text, split by commas or newlines
                raw_aliases = alias_div.get_text().replace("Aliases", "").strip()
                aliases = [a.strip() for a in re.split(r'[,;\n]', raw_aliases) if a.strip()]

        # 2. Scrape Personality (The Golden Standard)
        personality_text = "Personality not found."
        
        # Look for a header named "Personality", "Character", or "Philosophy"
        target_headers = ["Personality", "Character", "Philosophy", "Appearance and Personality"]
        
        for header_text in target_headers:
            header = soup.find(["h2", "h3"], string=re.compile(header_text, re.I))
            if header:
                # Gather all paragraphs until the next header
                content = []
                curr = header.find_next_sibling()
                while curr and curr.name not in ["h2", "h3"]:
                    if curr.name == "p":
                        content.append(curr.get_text().strip())
                    curr = curr.find_next_sibling()
                
                if content:
                    personality_text = "\n".join(content)
                    break
        
        # Clean footnotes
        personality_text = re.sub(r'\[.*?\]', '', personality_text)
        
        print(f"✅ Extracted Personality ({len(personality_text)} chars).")
        print(f"✅ Extracted {len(aliases)} Aliases.")

        return Character(
            name=char_name,
            novel_id=self.novel_id,
            description=f"Protagonist of {self.title}",
            aliases=aliases,
            role="Protagonist",
            wiki_profile_link=f"{self.base_url}/wiki/{endpoint}",
            base_personality=personality_text
        )

    def generate_namespace(self, char_name: str, cultivation_page: str) -> NovelNamespace:
        power_hierarchy = self.scrape_power_hierarchy(cultivation_page)
        
        # Save Character separately (optional, but good for debugging)
        main_char = self.scrape_character(char_name)
        
        # Save Main Character to disk immediately as a Golden Standard reference
        with open(f"data/{self.novel_id}_MC.json", "w", encoding="utf-8") as f:
            f.write(main_char.model_dump_json(indent=2))
            
        return NovelNamespace(
            novel_id=self.novel_id,
            title=self.title,
            wiki_url=self.base_url,
            power_hierarchy=power_hierarchy,
            known_factions=[], # Could be scraped similarly
            known_locations=[]
        )

def main():
    parser = argparse.ArgumentParser(description="Wiki Scraper for Infinite Library")
    parser.add_argument("--url", required=True, help="Base Fandom URL (e.g. https://martial-world.fandom.com)")
    parser.add_argument("--id", required=True, help="Novel ID (e.g. martial_world)")
    parser.add_argument("--title", required=True, help="Novel Title")
    parser.add_argument("--mc", required=True, help="Main Character Name (as in Wiki URL)")
    parser.add_argument("--cultivation", default="Cultivation", help="Endpoint for Cultivation page")
    
    args = parser.parse_args()

    scraper = FandomScraper(args.url, args.id, args.title)
    
    namespace = scraper.generate_namespace(args.mc, args.cultivation)
    
    output_path = f"data/{args.id}_namespace.json"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(namespace.model_dump_json(indent=2))
        
    print(f"✨ Namespace generated: {output_path}")
    print("👉 Validate this file manually before starting ingestion!")

if __name__ == "__main__":
    main()