import os
import subprocess

with open("/home/noob/barn/scan/delinquent_over_2_years.txt", "r") as f:
    apns = [line.strip() for line in f if line.strip()]

print(f"Found {len(apns)} properties for Oakland. Starting deep cyber research...")

for apn in apns:
    print(f"\n--- Researching {apn} ---")
    subprocess.run(["python", "cyber_research_agent.py", "--apn", apn])

print("Finished Oakland research loop.")
