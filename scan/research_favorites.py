import json
import asyncio
import logging
from pathlib import Path
from cyber_research_agent import run_agent, PropertyResearchInput, OPENROUTER_API_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def process_favorites():
    favs_path = Path("favs.json")
    if not favs_path.exists():
        logging.error("favs.json not found")
        return

    with open(favs_path, 'r') as f:
        targets = json.load(f)

    if not OPENROUTER_API_KEY:
        logging.error("OPENROUTER_API_KEY is missing. Add it to .env.")
        return

    for item in targets:
        apn = item.get("apn")
        address = item.get("address")
        city = item.get("city")
        current_owner = item.get("owner")
        
        # Skip if already found
        if current_owner and current_owner != "UNKNOWN" and current_owner != "ERROR" and current_owner != "ERROR_RESEARCH":
            continue

        full_addr = address
        if city:
             full_addr = f"{address}, {city}, CA"

        logging.info(f"Processing APN: {apn} Address: {full_addr}")
        
        ctx = PropertyResearchInput.from_apn(apn)
        if not ctx:
            logging.warning(f"Could not load full DB context for {apn}, using favs.json data")
            ctx = PropertyResearchInput(
                property_address=full_addr,
                mailing_address=full_addr,
                apn=apn
            )

        # Run each agent fully before moving to the next. The underlying script has
        # a playwright singleton that fails if hit concurrently by background tasks,
        # so we ensure strict sequencing here.
        success, report = await run_agent(ctx, verbose=False)
        
        if success:
            logging.info(f"Successfully generated report for {apn}")
            item["cyber_report"] = report
            import re
            match = re.search(r"\*\*Owner identification\*\*\s*[-–:]\s*(.+)", report, re.IGNORECASE)
            if match:
                item["owner"] = match.group(1).strip()
                logging.info(f"Extracted Owner: {item['owner']}")
            else:
                item["owner"] = "RESEARCHED_CHECK_REPORT"
        else:
            logging.error(f"Failed to generate report for {apn}: {report}")
            item["owner"] = "ERROR_RESEARCH"

        # Save after every property in case it crashes
        with open("favs_research.json", "w") as f:
            json.dump(targets, f, indent=2)

if __name__ == "__main__":
    asyncio.run(process_favorites())
