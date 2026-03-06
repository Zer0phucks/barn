from bs4 import BeautifulSoup
import re

with open("debug_last_scan.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

# Find Ownership Type
print("--- Property Facts ---")
for label in ["Ownership Type", "Last Sale Date", "Occupancy Type"]:
    element = soup.find(string=re.compile(label, re.IGNORECASE))
    if element:
        parent = element.parent
        print(f"Label: {label}")
        print(f"Parent HTML: {parent.prettify()}")
        # Check siblings
        next_sibling = parent.find_next_sibling()
        if next_sibling:
            print(f"Next sibling HTML: {next_sibling.prettify()}")
    else:
        print(f"Label '{label}' not found")
    print("-" * 20)

# Find Person Card Links
print("\n--- Person Card Links ---")
cards = soup.select("div.card")
print(f"Found {len(cards)} cards")

found_person = False
for i, card in enumerate(cards):
    if card.select_one(".name-primary") or card.select_one("span.name-given"):
        print(f"--- Person Card {i+1} ---")
        print(card.get_text(separator="|", strip=True))
        print("--- Links inside this card ---")
        links = card.find_all("a")
        for link in links:
             print(f"Text: '{link.get_text(strip=True)}'")
             print(f"Href: {link.get('href')}")
             print(f"Classes: {link.get('class')}")
        found_person = True
        break

if not found_person:
    print("No person card found with .name-primary or span.name-given")
