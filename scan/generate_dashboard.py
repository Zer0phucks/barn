import os
import db
import urllib.parse

def generate(city="OAKLAND"):
    client = db.get_client()
    input_file = f"delinquent_over_2_years_{city.lower()}.txt" if city != "OAKLAND" else "delinquent_over_2_years.txt"
    with open(input_file, "r") as f:
        apns = [line.strip() for line in f if line.strip()]
    
    properties = []
    for apn in apns:
        bill = db.get_bill_with_parcel(apn)
        if bill:
            properties.append(bill)

        
    google_api_key = os.environ.get("GOOGLE_API_KEY", "")
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Delinquent Properties Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .glass {
            background: rgba(255, 255, 255, 0.7);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.18);
        }
    </style>
</head>
<body class="bg-slate-100 min-h-screen text-slate-800">

    <header class="bg-indigo-600 text-white shadow-lg sticky top-0 z-50">
        <div class="container mx-auto px-6 py-4 flex justify-between items-center">
            <h1 class="text-3xl font-extrabold tracking-tight">Sheriff Sale Watch</h1>
            <span class="bg-indigo-800 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">{count} Properties</span>
        </div>
    </header>

    <main class="container mx-auto px-6 py-10">
        <div class="mb-8">
            <h2 class="text-2xl font-bold text-slate-800 mb-2">Properties (> 2 Years Delinquent)</h2>
            <p class="text-slate-500">The following properties in {city} have unpaid taxes over 2 years and are subject to potential tax default sale.</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
"""
    
    import json

    for prop in properties:
        apn = prop["apn"]
        address = prop.get("location_of_property") or f"Property {apn}"
        encoded_address = urllib.parse.quote_plus(address)
        # Use local Street View images already downloaded
        image_path = f"streetview_images/{apn}.jpg"
        if not os.path.exists(image_path):
            # Fallback to embedded interactive map if image not found
            fallback_embed = f"https://maps.google.com/maps?q={encoded_address}&t=k&z=19&output=embed"
            map_visual = f'<iframe width="100%" height="100%" frameborder="0" style="border:0;" src="{fallback_embed}" allowfullscreen></iframe>'
        else:
            map_visual = f'<img src="{image_path}" alt="Street view of {address}" class="object-cover w-full h-full group-hover:scale-110 transition-transform duration-500" loading="lazy" />'
            
        # Google maps search link when clicking
        maps_link = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
        
        # Power Status
        power = prop.get("power_status")
        power_badge = ""
        if power == "on":
            power_badge = '<span class="inline-block bg-green-500 text-white text-xs font-bold px-2 py-1 rounded shadow drop-shadow ml-2" title="Power On">⚡ On</span>'
        elif power == "off":
            power_badge = '<span class="inline-block bg-red-600 text-white text-xs font-bold px-2 py-1 rounded shadow drop-shadow ml-2" title="Power Off">⚡ Off</span>'
            
        # Mailing Address Check
        row_json = prop.get("row_json") or {}
        if isinstance(row_json, str):
            try:
                row_json = json.loads(row_json)
            except:
                row_json = {}
        mailing = row_json.get("MailingAddress") or ""
        out_of_state_star = ""
        if mailing:
            mailing_upper = mailing.upper()
            if not mailing_upper.endswith(" CA") and " CA " not in mailing_upper:
                out_of_state_star = '<span class="text-yellow-400 text-xl inline-block drop-shadow-md ml-1" title="Out of State Mailing Address">⭐</span>'
        
        last_sale = row_json.get("LatestDocumentDate") or "Unknown"
        if " " in last_sale and last_sale != "Unknown":
            last_sale = last_sale.split(" ")[0]
            
        html += f"""
            <a href="{maps_link}" target="_blank" class="group block overflow-hidden rounded-2xl bg-white shadow-md hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-1">
                <div class="relative h-48 w-full overflow-hidden bg-slate-200">
                    {map_visual}
                    <div class="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent pointer-events-none"></div>
                    <div class="absolute bottom-4 left-4 pointer-events-none flex items-center">
                        <span class="inline-block bg-red-500 text-white text-xs font-bold px-2 py-1 rounded shadow drop-shadow max-w-full">Defaulted</span>
                        {power_badge}
                    </div>
                </div>
                <div class="p-5">
                    <h3 class="text-lg font-bold text-slate-900 mb-1 truncate flex items-center" title="{address}">{address}{out_of_state_star}</h3>
                    <div class="flex items-center text-sm text-slate-500 font-medium mb-1">
                        <svg class="w-4 h-4 mr-1 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0m-5 8a2 2 0 100-4 2 2 0 000 4zm0 0c1.306 0 2.417.835 2.83 2M9 14a3.001 3.001 0 00-2.83 2M15 11h3m-3 4h2"></path></svg>
                        APN: {apn}
                    </div>
                    <div class="flex items-center text-sm text-slate-500 font-medium">
                        <svg class="w-4 h-4 mr-1 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                        Last Sale: {last_sale}
                    </div>
                </div>
            </a>
"""

    html += """
        </div>
    </main>

    <footer class="bg-white border-t border-slate-200 mt-12 py-8">
        <div class="container mx-auto px-6 text-center text-slate-500 text-sm">
            Generated by Scanner System • Data represents known >2 year delinquencies.
        </div>
    </footer>
</body>
</html>
"""
    
    output_file = f"dashboard_{city.lower()}.html" if city != "OAKLAND" else "dashboard.html"
    with open(output_file, "w") as f:
        html_output = html.replace("{count}", str(len(properties))).replace("{city}", city.capitalize())
        f.write(html_output)
        
    print(f"Generated {output_file} with {len(properties)} properties.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    import sys
    load_dotenv()
    city_arg = "OAKLAND"
    if len(sys.argv) > 1:
        city_arg = sys.argv[1].upper()
    generate(city_arg)
