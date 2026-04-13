import asyncio
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

async def test():
    client = genai.Client(api_key=api_key)
    prompt = "Find out if the owner of 404 SANTA CLARA AVE OAKLAND CA 94610 is deceased. Who is the owner?"
    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}],
        )
    )
    print(response.text)

asyncio.run(test())
